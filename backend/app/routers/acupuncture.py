"""腧穴字典路由"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.acupuncture import Acupoint
from app.models.dictionaries import DictionaryTerm
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.acupuncture import AcupointCreate, AcupointUpdate, AcupointResponse
from app.constants.acupoint_tags import ACUPOINT_TAG_DIMENSIONS, ACUPOINT_TAG_DIMENSION_BY_LABEL

router = APIRouter(prefix="/acupoints", tags=["针灸"])

# 词项无色标时的兜底调色板：按维度散列 + 序号取色，同一词条颜色恒定
TAG_FALLBACK_PALETTE = [
    "#4a90a4", "#2e7d6b", "#d6922a", "#a93226", "#8e44ad", "#34495e",
    "#4aa36e", "#b9770e", "#7f8c8d", "#c0392b", "#2c3e50", "#95a5a6",
]


def derive_tag_color(dimension: str, name: str, index: int) -> str:
    """未配置自定义颜色时，为词项派生一个稳定的默认色标。"""
    h = sum(ord(ch) for ch in f"{dimension}:{name}")
    return TAG_FALLBACK_PALETTE[(h + index) % len(TAG_FALLBACK_PALETTE)]


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
    """返回 来源/归经/部位 三个受控维度的词表（类型已改为自由文本，不在此列）。
    词项由 DictionaryTerm(term_type='acupoint_tag') 提供，字典为空时回退常量默认词表。
    每个词项附带 description(释义) 与 color(色标)，供前端选择时提示。"""
    terms = db.query(DictionaryTerm).filter(
        DictionaryTerm.term_type == "acupoint_tag", DictionaryTerm.is_active == True
    ).all()
    by_label: dict[str, list] = {}
    term_info: dict[str, dict] = {}
    for t in terms:
        if (t.category or "") not in ACUPOINT_TAG_DIMENSION_BY_LABEL:
            continue
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
                # 字典未配色（或种子尚未执行）时按维度名称派生稳定色标，保证下拉框圆点始终可见
                "color": term_info.get(n, {}).get("color") or derive_tag_color(key, n, i),
            }
            for i, n in enumerate(names)
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
    from sqlalchemy.exc import IntegrityError
    try:
        db.delete(row)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="该穴位已被处方引用，无法删除")
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
                if k != "name" and v is not None:
                    setattr(existing, k, v)
            updated += 1
        else:
            db.add(Acupoint(**item.model_dump()))
            imported += 1
    db.commit()
    return {"imported": imported, "updated": updated, "total": len(data)}