"""数据模板导入 / 导出路由

- GET  /templates              列出可导入的模板类型（含内置模板是否可用）
- GET  /templates/export/{type} 把当前库某类型数据导出为 JSON 模板（下载）
- POST /templates/import        导入模板：上传 JSON 文件，或指定 use_bundled 导入内置模板
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

router = APIRouter(prefix="/templates", tags=["数据模板"])


@router.get("", summary="列出可导入的模板类型")
def get_types(current_user: User = Depends(get_current_user)):
    return list_types()


@router.get("/export/{type_}", summary="导出当前数据为模板 JSON")
def export_type(
    type_: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    type_: str = Query(..., description="模板类型：herbs/classic_formulas/acupoint_formulas/acupoints/knowledge"),
    use_bundled: bool = Query(False, description="true 时导入内置模板文件（忽略上传文件）"),
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

    result = import_items(db, type_, items)
    return result
