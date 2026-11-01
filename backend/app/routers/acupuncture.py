"""腧穴字典路由"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.acupuncture import Acupoint
from app.models.dictionaries import DictionaryTerm
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.acupuncture import AcupointCreate, AcupointUpdate, AcupointResponse
from app.constants.acupoint_tags import ACUPOINT_TAG_DIMENSIONS

router = APIRouter(prefix="/acupoints", tags=["针灸"])


@router.get("", response_model=list[AcupointResponse], summary="腧穴列表")
def list_acupoints(
    meridian: str | None = None,
    region: str | None = None,
    source: str | None = None,
    point_type: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Acupoint)
    if meridian:
        query = query.filter(Acupoint.meridian == meridian)
    if region:
        query = query.filter(Acupoint.region == region)
    if source:
        query = query.filter(Acupoint.source == source)
    if point_type:
        query = query.filter(Acupoint.point_type == point_type)
    if search:
        query = query.filter(Acupoint.name.like(f"%{search}%"))
    return query.order_by(Acupoint.meridian, Acupoint.id).all()


@router.get("/tags/meta", summary="穴位属性维度与受控词表（来自数据字典）")
def acupoint_tag_meta(db: Session = Depends(get_db)):
    """参照 /herbs/tags/meta：返回 来源/归经/部位/类型 四个维度的受控词表，
    词项由 DictionaryTerm(term_type='acupoint_tag') 提供，字典为空时回退常量默认词表。
    每个词项附带 description(释义) 与 color(色标)，供前端选择时提示。"""
    terms = db.query(DictionaryTerm).filter(
        DictionaryTerm.term_type == "acupoint_tag", DictionaryTerm.is_active == True
    ).all()
    by_label: dict[str, list] = {}
    term_info: dict[str, dict] = {}
    for t in terms:
        by_label.setdefault(t.category or "", []).append(t.name)
        term_info[t.name] = {"description": t.description or "", "color": t.color or ""}
    dimensions: dict[str, dict] = {}
    for key, spec in ACUPOINT_TAG_DIMENSIONS.items():
        label = spec["label"]
        names = by_label.get(label) or spec.get("options", [])
        options = [
            {
                "value": n,
                "label": n,
                "description": term_info.get(n, {}).get("description", ""),
                "color": term_info.get(n, {}).get("color", ""),
            }
            for n in names
        ]
        dimensions[key] = {"label": label, "multi": spec["multi"], "options": options}
    return {"dimensions": dimensions, "tag_suggestions": []}


@router.post("", response_model=AcupointResponse, summary="新增腧穴")
def create_acupoint(data: AcupointCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.query(Acupoint).filter(Acupoint.name == data.name).first():
        raise HTTPException(status_code=400, detail=f"腧穴「{data.name}」已存在")
    row = Acupoint(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{acupoint_id}", response_model=AcupointResponse, summary="编辑腧穴")
def update_acupoint(acupoint_id: int, data: AcupointUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(Acupoint).filter(Acupoint.id == acupoint_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="腧穴不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{acupoint_id}", summary="删除腧穴")
def delete_acupoint(acupoint_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(Acupoint).filter(Acupoint.id == acupoint_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="腧穴不存在")
    db.delete(row)
    db.commit()
    return {"message": "已删除"}


@router.get("/export", response_model=list[AcupointResponse], summary="导出全量腧穴")
def export_acupoints(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Acupoint).order_by(Acupoint.meridian, Acupoint.id).all()


@router.post("/import", response_model=dict, summary="批量导入腧穴(按穴名 upsert)")
def import_acupoints(data: list[AcupointCreate] = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    imported, updated = 0, 0
    for item in data:
        existing = db.query(Acupoint).filter(Acupoint.name == item.name).first()
        if existing:
            for k, v in item.model_dump().items():
                if v is not None:
                    setattr(existing, k, v)
            updated += 1
        else:
            db.add(Acupoint(**item.model_dump()))
            imported += 1
    db.commit()
    return {"imported": imported, "updated": updated, "total": len(data)}