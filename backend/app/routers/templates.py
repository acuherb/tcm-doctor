"""数据模板导入 / 导出路由

- GET  /templates              列出可导入的模板类型（含内置模板是否可用）
- GET  /templates/export/{type} 把当前库某类型数据导出为 JSON 模板（下载）
- POST /templates/import        导入模板：上传 JSON 文件，或指定 use_bundled 导入内置模板
- GET  /templates/bundles       列出随安装包分发的基础数据包 + 内容库是否为空
- POST /templates/bundle/preview  基础数据包预检（manifest/sha256/依赖 + dry_run）
- POST /templates/bundle/install  基础数据包正式安装
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response

from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.permissions import has_perm
from app.templates import TEMPLATE_TYPES, list_types, export_template, import_items, _read_bundled
from app import template_bundle
from app.template_bundle import BundleError
from app.utils.operation_log import write_log

router = APIRouter(prefix="/templates", tags=["数据模板"])

# 上传模板体积上限（防止大文件打满内存）
MAX_TEMPLATE_BYTES = 50 * 1024 * 1024


@router.get("", summary="列出可导入的模板类型")
def get_types(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list_types(db)


@router.get("/export/{type_}", summary="导出当前数据为模板 JSON")
def export_type(
    type_: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 内容库全量导出属管理操作；模板清单/基础数据包安装仍对所有登录账号开放
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="仅管理员可导出内容库数据")
    if type_ not in TEMPLATE_TYPES:
        raise HTTPException(status_code=404, detail="未知模板类型")
    data = export_template(db, type_)
    body = json.dumps(data, ensure_ascii=False, indent=2)
    filename = f"tcm_template_{type_}.json"
    return Response(
        content=body.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/import", summary="导入模板（上传 JSON 或 使用内置模板）")
async def import_type(
    type_: str = Query(..., alias="type", description="模板类型：herbs/classic_formulas/acupoint_formulas/acupoints/knowledge"),
    use_bundled: bool = Query(False, description="true 时导入内置模板文件（忽略上传文件）"),
    dry_run: bool = Query(False, description="true 时仅预检，返回新增/更新/跳过计数，不写入"),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="仅管理员可导入数据模板")
    if type_ not in TEMPLATE_TYPES:
        raise HTTPException(status_code=404, detail="未知模板类型")

    if use_bundled:
        items = _read_bundled(TEMPLATE_TYPES[type_])
        if not items:
            raise HTTPException(status_code=404, detail="内置模板文件不存在（可能已被移除或未随发行包提供）")
    elif file is not None:
        content = await file.read()
        if len(content) > MAX_TEMPLATE_BYTES:
            raise HTTPException(status_code=413, detail="模板文件过大（上限 50MB）")
        try:
            parsed = json.loads(content.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="JSON 解析失败，请检查文件格式")
        if isinstance(parsed, dict) and "items" in parsed:
            items = parsed["items"]
        elif isinstance(parsed, list):
            items = parsed
        else:
            raise HTTPException(status_code=400, detail="模板格式应为 {\"items\": [...]} 或直接为 [...]")
    else:
        raise HTTPException(status_code=400, detail="请提供上传文件，或指定 use_bundled=true 导入内置模板")

    result = import_items(db, type_, items, dry_run=dry_run)
    return result


# ── 基础数据包一键导入 ──

@router.get("/bundles", summary="列出可用基础数据包与内容库状态")
def list_bundles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = list_types(db)
    counts = {c["type"]: c["count"] for c in content}
    # 「空框架」以用户内容库（药材 / 方库 / 医籍）为准：种子数据里的穴位字典不算内容包
    needs_setup = all(counts.get(t, 0) == 0 for t in ("herbs", "classic_formulas", "knowledge"))
    return {
        "packages": [d for d in (template_bundle.describe(p) for p in template_bundle.find_packages()) if d],
        "content": content,
        "needs_setup": needs_setup,
    }


async def _bundle_bytes(
    file: UploadFile | None, use_bundled: bool, name: str | None,
) -> bytes:
    if use_bundled:
        try:
            path = template_bundle.resolve_bundled(name or "")
        except BundleError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return path.read_bytes()
    if file is None:
        raise HTTPException(status_code=400, detail="请上传 .zip 基础数据包，或选择随包附带的数据包")
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="基础数据包需为 .zip 文件")
    data = await file.read()
    if len(data) > MAX_TEMPLATE_BYTES:
        raise HTTPException(status_code=413, detail="基础数据包过大（上限 50MB）")
    return data


def _bundle_plan(data: bytes, layers: str | None) -> dict:
    try:
        return template_bundle.build_plan(data, layers)
    except BundleError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _bundle_response(plan: dict, result: dict, dry_run: bool) -> dict:
    return {
        "dry_run": dry_run,
        "manifest": plan["manifest"],
        "order": plan["order"],
        "layers": plan["layers"],
        "warnings": plan["warnings"],
        "totals": result["totals"],
        "files": result["files"],
        "errors": result["errors"],
    }


@router.post("/bundle/preview", summary="基础数据包预检（不写入数据）")
async def preview_bundle(
    use_bundled: bool = Query(False, description="使用随包附带的数据包"),
    name: str | None = Query(None, description="内置数据包文件名"),
    layers: str | None = Query(None, description="逗号分隔的分层名；默认全部，依赖层会自动补上"),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="仅管理员可安装基础数据包")
    data = await _bundle_bytes(file, use_bundled, name)
    plan = _bundle_plan(data, layers)
    return _bundle_response(plan, template_bundle.apply_plan(db, plan, dry_run=True), dry_run=True)


@router.post("/bundle/install", summary="正式安装基础数据包")
async def install_bundle(
    use_bundled: bool = Query(False, description="使用随包附带的数据包"),
    name: str | None = Query(None, description="内置数据包文件名"),
    layers: str | None = Query(None, description="逗号分隔的分层名；默认全部，依赖层会自动补上"),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="仅管理员可安装基础数据包")
    data = await _bundle_bytes(file, use_bundled, name)
    plan = _bundle_plan(data, layers)
    result = template_bundle.apply_plan(db, plan, dry_run=False)
    write_log(level="INFO", user_id=current_user.id, username=current_user.username,
              action="安装基础数据包", endpoint="/api/v1/templates/bundle/install", method="POST",
              status_code=200, success=True,
              message=f"安装 {plan['manifest'].get('title') or '基础数据包'} "
                      f"v{plan['manifest'].get('version') or '-'}：新增 {result['totals']['added']}，"
                      f"更新 {result['totals']['updated']}，跳过 {result['totals']['skipped']}")
    return _bundle_response(plan, result, dry_run=False)
