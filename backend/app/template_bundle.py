"""基础数据包（分层 zip + manifest）一键导入。

设计要点：
- manifest.json 驱动：schema_version 校验、layers 依赖拓扑排序、按依赖顺序导入，避免引用悬空；
- 每个 JSON 文件按 manifest 的 sha256 校验完整性，条目数与 count 核对，类型必须在 TEMPLATE_TYPES 白名单内；
- zip 条目做路径穿越 / 解压体积限制，只读取白名单表，永不触碰 patients / prescriptions 等业务数据；
- 预检（dry_run）与正式安装走同一份 plan，保证「看到的就是要写入的」。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from pathlib import Path, PurePosixPath
from sqlalchemy.orm import Session

from app.templates import TEMPLATE_TYPES, import_items

SCHEMA_VERSION = 1
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_UNCOMPRESSED = 120 * 1024 * 1024


class BundleError(Exception):
    """数据包不合法（面向用户可读的错误信息）。"""


def _safe_entry(name: str) -> bool:
    if not name or name.startswith(("/", "\\")) or "\\" in name:
        return False
    parts = PurePosixPath(name).parts
    return ".." not in parts and not PurePosixPath(name).is_absolute()


def _read_manifest(z: zipfile.ZipFile) -> dict:
    try:
        raw = z.read("manifest.json")
    except KeyError:
        raise BundleError("数据包缺少 manifest.json")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except Exception:
        raise BundleError("manifest.json 解析失败")
    if not isinstance(manifest, dict):
        raise BundleError("manifest.json 格式应为对象")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise BundleError(
            f"数据包 schema_version={manifest.get('schema_version')}，本系统仅支持 {SCHEMA_VERSION}"
        )
    if not isinstance(manifest.get("layers"), list) or not manifest["layers"]:
        raise BundleError("manifest.json 缺少 layers 分层定义")
    return manifest


def _candidate_dirs() -> list[Path]:
    root = Path(__file__).resolve().parents[2]
    return [
        root / "templates" / "releases",
        Path.cwd() / "templates" / "releases",
        Path.cwd(),
        root,
    ]


def find_packages() -> list[Path]:
    """找出随安装包分发 / 用户放置的基础数据包（只认带合法 manifest 的 zip）。"""
    explicit = os.environ.get("TCM_BASE_PACKAGE", "").strip()
    candidates: list[Path] = [Path(explicit)] if explicit else []
    seen: set[str] = set()
    for d in _candidate_dirs():
        try:
            for p in sorted(d.glob("*.zip")):
                key = str(p.resolve())
                if key not in seen:
                    seen.add(key)
                    candidates.append(p)
        except OSError:
            continue
    return [p for p in candidates if p.is_file() and describe(p) is not None]


def resolve_bundled(name: str) -> Path:
    """按文件名解析内置数据包；不接受路径，避免读取任意文件。"""
    if not name or Path(name).name != name:
        raise BundleError("非法的数据包名称")
    for p in find_packages():
        if p.name == name:
            return p
    raise BundleError("内置基础数据包不存在")


def describe(path: Path) -> dict | None:
    """读取包清单摘要，供界面列出可用数据包（不含条目内容）。"""
    try:
        with zipfile.ZipFile(path) as z:
            manifest = _read_manifest(z)
    except (BundleError, zipfile.BadZipFile, OSError, ValueError):
        return None
    layers = []
    for layer in manifest["layers"]:
        if not isinstance(layer, dict):
            continue
        files = layer.get("files") or []
        layers.append({
            "name": str(layer.get("name") or ""),
            "label": str(layer.get("label") or layer.get("name") or ""),
            "depends_on": [str(x) for x in (layer.get("depends_on") or [])],
            "types": [str(x) for x in (layer.get("types") or [])],
            "files": len(files),
            "count": sum(f.get("count", 0) for f in files if isinstance(f, dict)),
        })
    return {
        "name": path.name,
        "size": path.stat().st_size,
        "title": manifest.get("title") or path.stem,
        "version": manifest.get("version") or "",
        "source": manifest.get("source") or "",
        "schema_version": manifest.get("schema_version"),
        "layers": layers,
    }


def _topological_order(defs: dict[str, dict]) -> list[str]:
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(name: str) -> None:
        if state.get(name) == 1:
            raise BundleError(f"分层依赖存在循环：{name}")
        if state.get(name) == 2:
            return
        state[name] = 1
        for dep in defs[name].get("depends_on") or []:
            if dep not in defs:
                raise BundleError(f"分层 {name} 依赖的 {dep} 不存在")
            visit(str(dep))
        state[name] = 2
        order.append(name)

    for name in defs:
        visit(name)
    return order


def build_plan(data: bytes, layers_arg: str | None = None) -> dict:
    """校验数据包并生成导入计划；任何致命问题抛 BundleError，不产生任何写入。"""
    if not data:
        raise BundleError("数据包为空")
    if len(data) > MAX_ZIP_BYTES:
        raise BundleError("数据包过大（上限 50MB）")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise BundleError("不是合法的 zip 数据包")

    with z:
        for name in z.namelist():
            if not _safe_entry(name):
                raise BundleError(f"数据包含非法路径：{name}")
        if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED:
            raise BundleError("数据包解压后体积过大")

        manifest = _read_manifest(z)
        defs: dict[str, dict] = {}
        for layer in manifest["layers"]:
            if not isinstance(layer, dict) or not layer.get("name"):
                raise BundleError("manifest.json 中存在缺少 name 的分层")
            defs[str(layer["name"])] = layer
        order = _topological_order(defs)

        if layers_arg:
            wanted = [s.strip() for s in layers_arg.split(",") if s.strip()]
            unknown = [s for s in wanted if s not in defs]
            if unknown:
                raise BundleError(f"未知分层：{', '.join(unknown)}")
            selected = set(wanted)
            # 自动补上依赖层，保证「先 core 后 formulas/books」
            pending = list(selected)
            while pending:
                cur = pending.pop()
                for dep in defs[cur].get("depends_on") or []:
                    if dep not in selected:
                        selected.add(dep)
                        pending.append(dep)
        else:
            selected = set(defs)

        files: list[dict] = []
        warnings: list[str] = []
        for layer_name in order:
            if layer_name not in selected:
                continue
            layer = defs[layer_name]
            types = layer.get("types") or []
            entries = layer.get("files") or []
            for idx, entry in enumerate(entries):
                rel = entry.get("file") if isinstance(entry, dict) else entry
                if not isinstance(rel, str) or not _safe_entry(rel):
                    raise BundleError(f"分层 {layer_name} 含非法文件路径")
                try:
                    raw = z.read(rel)
                except KeyError:
                    raise BundleError(f"数据包缺少文件：{rel}")
                if len(raw) > MAX_FILE_BYTES:
                    raise BundleError(f"{rel} 体积过大")

                declared_hash = entry.get("sha256") if isinstance(entry, dict) else None
                if declared_hash:
                    actual = hashlib.sha256(raw).hexdigest()
                    if actual != str(declared_hash):
                        raise BundleError(f"{rel} 校验失败：sha256 不匹配，文件可能损坏或被改动")
                else:
                    warnings.append(f"{rel} 未声明 sha256，已跳过完整性校验")

                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception:
                    raise BundleError(f"{rel} JSON 解析失败")
                items = payload.get("items") if isinstance(payload, dict) else payload
                if not isinstance(items, list):
                    raise BundleError(f"{rel} 应为 {{\"items\": [...]}} 或直接为数组")
                declared_count = entry.get("count") if isinstance(entry, dict) else None
                if isinstance(declared_count, int) and declared_count != len(items):
                    raise BundleError(
                        f"{rel} 条目数不符（清单声明 {declared_count}，实际 {len(items)}）"
                    )

                type_ = types[idx] if idx < len(types) else PurePosixPath(rel).stem
                if type_ not in TEMPLATE_TYPES:
                    raise BundleError(f"{rel} 的类型 {type_} 不在允许导入的白名单内")

                files.append({
                    "layer": layer_name,
                    "file": rel,
                    "type": type_,
                    "label": layer.get("label") or layer_name,
                    "count": len(items),
                    "sha256_verified": bool(declared_hash),
                    "items": items,
                })

        if not files:
            raise BundleError("所选分层没有可导入的内容文件")

    return {
        "manifest": {
            "package": manifest.get("package") or "",
            "title": manifest.get("title") or "",
            "version": manifest.get("version") or "",
            "source": manifest.get("source") or "",
            "schema_version": manifest.get("schema_version"),
        },
        "order": [n for n in order if n in selected],
        "layers": [
            {
                "name": n,
                "label": defs[n].get("label") or n,
                "depends_on": defs[n].get("depends_on") or [],
                "count": sum(f["count"] for f in files if f["layer"] == n),
            }
            for n in order if n in selected
        ],
        "files": files,
        "warnings": warnings,
    }


def apply_plan(db: Session, plan: dict, dry_run: bool) -> dict:
    """按 plan 顺序导入（dry_run 时仅预检，不落库）。"""
    totals = {"created": 0, "updated": 0, "skipped": 0}
    files: list[dict] = []
    errors: list[str] = []
    for f in plan["files"]:
        result = import_items(db, f["type"], f["items"], dry_run=dry_run)
        for key in totals:
            totals[key] += result[key]
        errors.extend(f"{f['file']}: {e}" for e in result["errors"][:3])
        files.append({
            "layer": f["layer"], "file": f["file"], "type": f["type"],
            "count": f["count"], "sha256_verified": f["sha256_verified"],
            "created": result["created"], "updated": result["updated"],
            "skipped": result["skipped"],
        })
    return {"totals": totals, "files": files, "errors": errors[:20]}
