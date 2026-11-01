"""药品管理路由（仅药材字典；库存/批次/流水见 stock 路由）"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.herb import Herb
from app.models.dictionaries import DictionaryTerm
from app.models.prescription import PrescriptionItem
from app.models.user import User
from app.routers.auth import get_current_user
from app.constants.herb_tags import sanitize_herb_tags
from app.schemas.herb import (
    HerbCreate, HerbUpdate, HerbResponse,
)

router = APIRouter(prefix="/herbs", tags=["药品管理"])


# ── 药材字典 CRUD ──

@router.get("", response_model=list[HerbResponse], summary="药材列表（多维标签筛选）")
def list_herbs(
    search: str | None = Query(None, description="搜索(正名/异名/主治)"),
    is_active: bool | None = Query(None, description="是否启用"),
    nature: str | None = Query(None, description="四气"),
    flavors: list[str] | None = Query(None, description="五味(多值, 须全部具备)"),
    pregnancy_contraindicated: bool | None = Query(None, description="仅看孕妇禁忌药"),
    db: Session = Depends(get_db),
):
    query = db.query(Herb)
    if is_active is not None:
        query = query.filter(Herb.is_active == is_active)
    herbs = query.all()

    def matches(h: Herb) -> bool:
        if nature and h.nature != nature:
            return False
        if flavors and not set(flavors).issubset(set(h.flavors or [])):
            return False
        if pregnancy_contraindicated is not None and h.pregnancy_contraindicated != pregnancy_contraindicated:
            return False
        if search:
            q = search.lower()
            if not (
                q in (h.name or "").lower()
                or any(q in (a or "").lower() for a in (h.aliases or []))
                or (h.efficacy and q in h.efficacy.lower())
            ):
                return False
        return True

    herbs = [h for h in herbs if matches(h)]
    herbs.sort(key=lambda h: h.name or "")
    return herbs


@router.get("/tags/meta", summary="药材标签维度与受控词表（来自数据字典）")
def herb_tag_meta(db: Session = Depends(get_db)):
    """返回标签维度（三品/四气/五味/归经/升降浮沉）的受控词表，词表来源为数据字典
    DictionaryTerm(term_type='herb_tag', category=维度中文名)；字典为空时回退到常量默认词表。
    通用标签(tags)为自由标注，不再提供受控建议。"""
    from app.constants.herb_tags import HERB_TAG_DIMENSIONS

    terms = db.query(DictionaryTerm).filter(
        DictionaryTerm.term_type == "herb_tag", DictionaryTerm.is_active == True
    ).all()
    by_label: dict[str, list] = {}
    term_info: dict[str, dict] = {}
    for t in terms:
        by_label.setdefault(t.category or "", []).append(t.name)
        term_info[t.name] = {"description": t.description or "", "color": t.color or ""}

    dimensions = {}
    for key, spec in HERB_TAG_DIMENSIONS.items():
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


def _herb_tag_allowed(db: Session) -> dict:
    """从数据字典读取 herb_tag 各维度的受控词表（按中文维度名归类），供写入校验使用。"""
    from app.constants.herb_tags import HERB_TAG_DIMENSION_BY_LABEL

    terms = db.query(DictionaryTerm).filter(
        DictionaryTerm.term_type == "herb_tag", DictionaryTerm.is_active == True
    ).all()
    by_label: dict[str, set] = {}
    for t in terms:
        by_label.setdefault(t.category or "", set()).add(t.name)
    return {dim_key: by_label.get(label, set()) for label, dim_key in HERB_TAG_DIMENSION_BY_LABEL.items()}


@router.post("", response_model=HerbResponse, summary="新增药材")
def create_herb(data: HerbCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(Herb).filter(Herb.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"药材'{data.name}'已存在")
    payload = sanitize_herb_tags(data.model_dump(), _herb_tag_allowed(db))
    herb = Herb(**payload)
    db.add(herb)
    db.commit()
    db.refresh(herb)
    return herb


# ── 药材字典 导入/导出（固定路径必须先于 /{herb_id} 定义）──

@router.get("/export", response_model=list[HerbResponse], summary="导出药材字典(JSON)")
def export_herbs(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """导出全量药材字典，用于迁移/备份/手工批量预置"""
    return db.query(Herb).order_by(Herb.name).all()


@router.post("/import", summary="导入药材字典(JSON，按正名 upsert)")
def import_herbs(data: list[HerbCreate] = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """按正名 upsert：已存在则更新字段，不存在则新增"""
    imported = updated = 0
    allowed = _herb_tag_allowed(db)
    for item in data:
        existing = db.query(Herb).filter(Herb.name == item.name).first()
        payload = sanitize_herb_tags(item.model_dump(), allowed)
        if existing:
            for key, value in payload.items():
                if value is not None:
                    setattr(existing, key, value)
            updated += 1
        else:
            db.add(Herb(**payload))
            imported += 1
    db.commit()
    return {"imported": imported, "updated": updated, "total": imported + updated}


# ── 药材详情/更新（路径参数路由，必须放在所有固定路径路由之后）──

@router.get("/{herb_id}", response_model=HerbResponse, summary="药材详情")
def get_herb(herb_id: int, db: Session = Depends(get_db)):
    herb = db.query(Herb).filter(Herb.id == herb_id).first()
    if not herb:
        raise HTTPException(status_code=404, detail="药材不存在")
    return herb


@router.put("/{herb_id}", response_model=HerbResponse, summary="更新药材")
def update_herb(herb_id: int, data: HerbUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    herb = db.query(Herb).filter(Herb.id == herb_id).first()
    if not herb:
        raise HTTPException(status_code=404, detail="药材不存在")
    payload = sanitize_herb_tags(data.model_dump(exclude_unset=True), _herb_tag_allowed(db))
    for key, value in payload.items():
        setattr(herb, key, value)
    db.commit()
    db.refresh(herb)
    return herb


@router.delete("/{herb_id}", summary="删除药材")
def delete_herb(herb_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """存在库存/处方引用时软删除(停用)，否则物理删除"""
    herb = db.query(Herb).filter(Herb.id == herb_id).first()
    if not herb:
        raise HTTPException(status_code=404, detail="药材不存在")
    from app.models.stock import StockItem, StockBatch
    ref_inv = db.query(StockBatch).join(StockItem).filter(StockItem.herb_id == herb_id).first()
    ref_item = db.query(PrescriptionItem).filter(PrescriptionItem.herb_id == herb_id).first()
    if ref_inv or ref_item:
        herb.is_active = False
        db.commit()
        return {"deleted": False, "soft": True, "message": "存在库存/处方引用，已改为停用"}
    db.delete(herb)
    db.commit()
    return {"deleted": True, "soft": False, "message": "已删除"}