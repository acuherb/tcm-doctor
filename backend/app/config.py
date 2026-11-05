"""应用配置管理"""
import sys
import os
import subprocess
from pydantic_settings import BaseSettings


# 容器内统一数据目录：数据库与 .env 配置都落在此处，挂载该目录即可持久化。
# 开发模式不设置 DATA_DIR，数据落在项目目录内。
# 桌面（PyInstaller frozen）模式默认落到用户目录，避免写入安装目录（Windows 下 Program Files 只读）。
_DATA_DIR = os.environ.get("DATA_DIR", "")

if not _DATA_DIR and getattr(sys, "frozen", False):
    _base = os.environ.get("APPDATA") or os.path.expanduser(
        "~/Library/Application Support" if sys.platform == "darwin" else "~/.local/share"
    )
    _DATA_DIR = os.path.join(_base, "tcm-doctor")
    os.makedirs(_DATA_DIR, exist_ok=True)

def _get_env_file() -> str:
    """PyInstaller 打包后 .env 优先放数据目录，其次 exe 同目录；容器内部优先放 DATA_DIR；开发时项目根目录"""
    if _DATA_DIR:
        return os.path.join(_DATA_DIR, '.env')
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), '.env')
    return ".env"


def resolve_env_path() -> "Path":
    """统一解析 .env 路径（兼顾 PyInstaller frozen / DATA_DIR / 开发三场景），供 main.py 等复用，避免重复实现导致构建不一致。"""
    from pathlib import Path
    return Path(_get_env_file())


class Settings(BaseSettings):
    """应用配置"""

    # 应用信息
    app_name: str = "中医诊所管理平台"
    app_version: str = "1.0.0"

    # 诊所信息（用于处方笺抬头、门诊病历落款等）
    clinic_name: str = ""
    doctor_name: str = ""
    # 诊所 logo（data URL，如 data:image/png;base64,xxx），用于浏览器标签图标/登录页展示
    clinic_logo: str = ""

    # 界面风格（herbal 本草 / ink 墨色 / vermilion 朱砂 / jade 青玉）
    ui_theme: str = "herbal"

    # 数据库（容器内默认落到 DATA_DIR=/data，挂载后持久化；开发/桌面默认项目内）
    database_url: str = (
        f"sqlite:///{_DATA_DIR}/tcm_doctor.db" if _DATA_DIR else "sqlite:///./tcm_doctor.db"
    )

    # DeepSeek API
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Vision API（图片识别，支持 OpenAI 兼容格式的 Vision 端点）
    deepseek_vision_model: str = ""  # 留空则不支持图片，如 Pro/moonshotai/Kimi-K2.6
    deepseek_vision_base_url: str = ""  # 留空则与 deepseek_base_url 相同
    deepseek_vision_api_key: str = ""  # 留空则复用 deepseek_api_key

    # 向量数据库
    chroma_persist_dir: str = f"{_DATA_DIR}/chroma_data" if _DATA_DIR else "./chroma_data"
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    # 语义检索需安装 chromadb + sentence-transformers 并下载中文向量模型；
    # 关闭时系统使用关键词检索（默认，轻量、无需大模型依赖）
    enable_semantic_search: bool = False

    # 服务配置
    host: str = "127.0.0.1"
    port: int = 8765

    # 安全
    # 游客免密登录（仅浏览，写操作仍受限）；默认关闭，所有接口均需登录后访问
    allow_guest_login: bool = False

    # 处方电子签名密钥：绑定「内容哈希 + 签名医师 + 签名时间」生成签名令牌，
    # 校验签名/防篡改时复用；生产环境请通过环境变量 TCM_SIGNING_SECRET 覆盖为强随机值。
    signing_secret: str = "tcm-doctor-default-signing-secret"

    # 操作日志保留天数：启动时自动清理超期日志，防止日志表无限增长；
    # 设为 0 表示不自动清理（仍可在界面手动清理）
    log_retention_days: int = 180

    # 自动备份（.env 可覆盖；界面里的开关/间隔/保留份数另存于 backups/auto_backup.json）
    # 默认开启：小型诊所/个人使用最怕「数据只存一份」，按天留快照，最多保留 7 份
    backup_auto_enabled: bool = True
    backup_interval_hours: int = 24
    backup_keep: int = 7
    # 留空则落在数据库同目录的 backups/ 下；容器/桌面可指向持久化目录
    backup_dir: str = ""

    model_config = {
        "env_file": _get_env_file(),
        "env_file_encoding": "utf-8",
    }


settings = Settings()

# 项目根目录（git 仓库根）
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git_head_short() -> str:
    """返回当前 git 提交的短哈希；非 git 环境或出错时返回空串。"""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
            cwd=_APP_ROOT,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


# 打包（PyInstaller/容器）或非 git 环境下跳过，避免额外开销与误判
_GIT_HEAD_SHORT = "" if getattr(sys, "frozen", False) else _git_head_short()


def build_display_version() -> str:
    """供系统信息展示的版本号：配置版本 + 当前 git 提交短哈希（无 git 环境时仅配置版本）。"""
    if _GIT_HEAD_SHORT:
        return f"{settings.app_version} ({_GIT_HEAD_SHORT})"
    return settings.app_version