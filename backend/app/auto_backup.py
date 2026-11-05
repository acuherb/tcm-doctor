"""SQLite 在线自动备份。

- 用 sqlite3.Connection.backup() 做在线快照：应用运行中也安全，且会带上 WAL 中尚未合并的写入。
- 守护线程按间隔执行（启动时先做一次），配置改动可即时重启线程。
- 按保留份数清理旧快照，至少保留最近 1 份；配置另存 JSON，避免改动 .env 才能调开关。
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.services import backup_crypto

logger = logging.getLogger(__name__)

PREFIX = "tcm_auto_"
CONFIG_FILENAME = "auto_backup.json"
_Lock = threading.Lock()
_STOP = threading.Event()
_THREAD: threading.Thread | None = None


def db_path() -> Path:
    raw = settings.database_url.replace("sqlite:///", "", 1)
    p = Path(raw)
    return p if p.is_absolute() else Path.cwd() / p


def backup_dir() -> Path:
    raw = (getattr(settings, "backup_dir", "") or "").strip()
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = Path.cwd() / p
    else:
        p = db_path().parent / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _config_path() -> Path:
    return backup_dir() / CONFIG_FILENAME


def _defaults() -> dict:
    return {
        "enabled": bool(getattr(settings, "backup_auto_enabled", True)),
        "interval_hours": max(1, int(getattr(settings, "backup_interval_hours", 24) or 24)),
        "keep": max(1, min(100, int(getattr(settings, "backup_keep", 7) or 7))),
    }


def load_config() -> dict:
    """配置 = .env 默认值 + 界面覆盖值；文件损坏时安全回退到默认值。"""
    cfg = _defaults()
    try:
        saved = json.loads(_config_path().read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            for key in cfg:
                if key in saved and isinstance(saved[key], type(cfg[key])):
                    cfg[key] = saved[key]
    except (OSError, ValueError):
        pass
    cfg["interval_hours"] = max(1, min(720, int(cfg["interval_hours"])))
    cfg["keep"] = max(1, min(100, int(cfg["keep"])))
    return cfg


def save_config(patch: dict) -> dict:
    """校验并持久化界面配置，返回生效后的完整配置。"""
    cfg = load_config()
    for key in ("enabled", "interval_hours", "keep"):
        if key in patch and patch[key] is not None:
            cfg[key] = patch[key]
    cfg["enabled"] = bool(cfg["enabled"])
    cfg["interval_hours"] = max(1, min(720, int(cfg["interval_hours"])))
    cfg["keep"] = max(1, min(100, int(cfg["keep"])))

    path = _config_path()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return cfg


def list_backups() -> list[dict]:
    """按时间倒序列出本功能生成的快照，不触碰用户手动放在该目录的其它文件。"""
    out: list[dict] = []
    try:
        files = backup_dir().glob(f"{PREFIX}*.db")
        for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
            st = f.stat()
            # 只列出完整快照：明文校验 SQLite magic，密文校验加密魔数；半截文件直接跳过
            try:
                with f.open("rb") as fp:
                    head = fp.read(16)
            except OSError:
                continue
            if not head.startswith(b"SQLite format 3\x00") and not head.startswith(backup_crypto.MAGIC):
                continue
            out.append({
                "name": f.name,
                "size": st.st_size,
                "created_at": datetime.fromtimestamp(st.st_mtime).isoformat(sep=" ", timespec="seconds"),
            })
    except OSError as e:
        logger.warning(f"读取自动备份列表失败: {e}")
    return out


def _prune(keep: int) -> int:
    files = sorted(backup_dir().glob(f"{PREFIX}*.db"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for f in files[max(1, int(keep)):]:
        try:
            f.unlink()
            removed += 1
        except OSError as e:
            logger.warning(f"清理旧备份失败 {f.name}: {e}")
    return removed


def create_backup(reason: str = "manual") -> dict:
    """生成一份在线快照；先写临时文件再原子改名，避免留下半截备份。"""
    src = db_path()
    if not src.is_file():
        raise FileNotFoundError(f"数据库文件不存在：{src}")

    tag = "manual" if reason == "manual" else "auto"
    name = f"{PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{tag}.db"
    target = backup_dir() / name
    tmp = backup_dir() / f"{name}.{os.getpid()}.tmp"

    with _Lock:
        source = dest = None
        try:
            # as_uri() 负责转义路径中的空格/中文；mode=ro 避免备份过程写源库
            source = sqlite3.connect(src.resolve().as_uri() + "?mode=ro", uri=True)
            dest = sqlite3.connect(str(tmp))
            source.backup(dest)
            # 快照不携带会话令牌：备份文件外流不应等价于「拿到管理员会话」。
            # 恢复备份后所有账号需重新登录，业务数据不受影响。
            try:
                dest.execute("DELETE FROM auth_tokens")
                dest.commit()
            except sqlite3.OperationalError:
                pass  # 老库尚无该表时忽略
            dest.close()
            dest = None
            source.close()
            source = None
            raw = tmp.read_bytes()
            if not raw[:16].startswith(b"SQLite format 3\x00"):
                raise RuntimeError("快照校验失败：不是合法的 SQLite 文件")
            # 启用备份加密时产出密文（含魔数头），否则明文；旧明文备份仍可恢复
            payload = backup_crypto.maybe_encrypt(raw)
            # 原子落盘：加密/写入中途失败只留下 .tmp，不会把半截文件当成有效快照
            tmp.write_bytes(payload)
            os.replace(tmp, target)
        finally:
            if dest is not None:
                dest.close()
            if source is not None:
                source.close()
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    st = target.stat()
    return {
        "name": name,
        "size": st.st_size,
        "created_at": datetime.fromtimestamp(st.st_mtime).isoformat(sep=" ", timespec="seconds"),
        "reason": tag,
    }


def run_cycle(force: bool = False) -> dict | None:
    """一次定时/手动备份周期：生成快照后按保留份数清理。"""
    cfg = load_config()
    if not cfg["enabled"] and not force:
        return None
    info = create_backup("auto" if not force else "manual")
    info["pruned"] = _prune(cfg["keep"])
    return info


def _loop() -> None:
    while not _STOP.is_set():
        cfg = load_config()
        if cfg["enabled"]:
            try:
                run_cycle()
            except Exception as e:
                logger.warning(f"自动备份失败（不影响应用运行）: {e}")
        if _STOP.wait(max(1, int(cfg["interval_hours"])) * 3600):
            break


def start() -> None:
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, name="tcm-auto-backup", daemon=True)
    _THREAD.start()
    logger.info("自动备份已启动")


def stop() -> None:
    _STOP.set()
    if _THREAD and _THREAD.is_alive():
        _THREAD.join(timeout=2)


def restart() -> None:
    """配置变更后让新间隔/开关立即生效。"""
    stop()
    start()
