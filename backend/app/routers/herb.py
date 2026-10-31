"""药品管理路由"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.herb import Herb, HerbInventory, InventoryTransaction
from app.models.dictionaries import DictionaryTerm
from app.models.prescription import PrescriptionItem
from app.models.user import User
from app.routers.auth import get_current_user
from app.constants.herb_tags import sanitize_herb_tags
from app.schemas.herb import (
    HerbCreate, HerbUpdate, HerbResponse,
    InventoryIn, InventoryOut, InventoryResponse, InventoryAlert, InventoryUpdate, InventorySummary,
)

router = APIRouter(prefix="/herbs", tags=["药品管理"])


# ── 药材字典 CRUD ──

@router.get("", response_model=list[HerbResponse], summary="药材列表（多维标签筛选）")
def list_herbs(
    search: str | None = Query(None, description="搜索(正名/异名/主治)"),
    is_active: bool | None = Query(None, description="是否启用"),
    nature: str | None = Query(None, description="四气"),
    flavors: list[str] | None = Query(None, description="五味(多值, 命中任一)"),
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
        if flavors and not (set(h.flavors or []) & set(flavors)):
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
    for t in terms:
        by_label.setdefault(t.category or "", []).append(t.name)

    dimensions = {}
    for key, spec in HERB_TAG_DIMENSIONS.items():
        label = spec["label"]
        opts = by_label.get(label) or spec.get("options", [])
        dimensions[key] = {"label": label, "multi": spec["multi"], "options": opts}
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


# ── 库存管理（必须在 /{herb_id} 之前定义，否则 inventory 会被当作 herb_id 匹配）──

@router.get("/inventory", response_model=list[InventoryResponse], summary="库存列表")
def list_inventory(
    search: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(HerbInventory).options(joinedload(HerbInventory.herb))
    if status:
        query = query.filter(HerbInventory.status == status)
    items = query.all()
    result = []
    for item in items:
        resp = InventoryResponse.model_validate(item)
        resp.herb_name = item.herb.name if item.herb else None
        result.append(resp)
    return result


@router.post("/inventory/in", response_model=InventoryResponse, summary="入库")
def inventory_in(data: InventoryIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    herb = db.query(Herb).filter(Herb.id == data.herb_id).first()
    if not herb:
        raise HTTPException(status_code=404, detail="药材不存在")

    # 查找或创建库存记录
    inv = HerbInventory(
        herb_id=data.herb_id,
        batch_number=data.batch_number,
        quantity=data.quantity,
        unit_price=data.unit_price,
        sale_price=data.sale_price,
        purchase_date=data.purchase_date,
        expiry_date=data.expiry_date,
        supplier=data.supplier,
        min_stock=0,
    )
    db.add(inv)
    db.flush()

    # 入库时填的售价同步到药材参考单价(元/g)，供处方计价与编辑器预估单价使用
    if data.sale_price is not None:
        herb.price = data.sale_price

    # 记录出入库
    txn = InventoryTransaction(
        herb_id=data.herb_id,
        transaction_type="入库",
        quantity=data.quantity,
        before_quantity=0,
        after_quantity=data.quantity,
        note=data.note,
    )
    db.add(txn)
    db.commit()
    db.refresh(inv)

    resp = InventoryResponse.model_validate(inv)
    resp.herb_name = herb.name
    return resp


@router.post("/inventory/out", summary="出库")
def inventory_out(data: InventoryOut, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """出库：从库存中扣减指定数量（进程内锁 + 行锁，避免并发超卖）"""
    from app.database import inventory_lock

    with inventory_lock:
        # 获取该药材总库存（加行锁，避免并发读-改-写竞态）
        total = db.query(HerbInventory).filter(
            HerbInventory.herb_id == data.herb_id,
            HerbInventory.status == "正常",
        ).with_for_update().all()
        available = sum(float(item.quantity) for item in total)

        if available < data.quantity:
            raise HTTPException(status_code=400, detail=f"库存不足: 可用{available}g，需{data.quantity}g")

        # 按批次先进先出扣减
        remaining = data.quantity
        for item in total:
            if remaining <= 0:
                break
            deduct = min(float(item.quantity), remaining)
            item.quantity = float(item.quantity) - deduct
            remaining -= deduct

        # 记录出入库
        txn = InventoryTransaction(
            herb_id=data.herb_id,
            transaction_type="出库",
            quantity=data.quantity,
            before_quantity=available,
            after_quantity=available - data.quantity,
            reference_id=data.reference_id,
            note=data.note,
        )
        db.add(txn)
        db.commit()
    return {"message": "出库成功", "quantity": data.quantity, "remaining": available - data.quantity}


@router.get("/inventory/alerts", response_model=list[InventoryAlert], summary="库存预警")
def inventory_alerts(db: Session = Depends(get_db)):
    """低于最低库存的药材预警"""
    items = db.query(HerbInventory).options(joinedload(HerbInventory.herb)).filter(
        HerbInventory.min_stock > 0,
    ).all()

    alerts = []
    for item in items:
        if float(item.quantity) < float(item.min_stock or 0):
            alerts.append(InventoryAlert(
                herb_id=item.herb_id,
                herb_name=item.herb.name if item.herb else "未知",
                current_quantity=float(item.quantity),
                min_stock=float(item.min_stock or 0),
                alert_type="低于最低库存",
            ))
    return alerts


@router.get("/inventory/summary", response_model=list[InventorySummary], summary="库存汇总")
def inventory_summary(db: Session = Depends(get_db)):
    """按药材汇总库存"""
    from sqlalchemy import func as sqlfunc
    results = db.query(
        HerbInventory.herb_id,
        sqlfunc.sum(HerbInventory.quantity).label("total_quantity"),
        sqlfunc.count(HerbInventory.id).label("batch_count"),
        sqlfunc.max(HerbInventory.min_stock).label("min_stock"),
    ).filter(
        HerbInventory.status == "正常",
    ).group_by(HerbInventory.herb_id).all()

    herb_ids = [r.herb_id for r in results]
    herbs_map = {}
    if herb_ids:
        herbs_list = db.query(Herb).filter(Herb.id.in_(herb_ids)).all()
        herbs_map = {h.id: h.name for h in herbs_list}

    return [
        InventorySummary(
            herb_id=r.herb_id,
            herb_name=herbs_map.get(r.herb_id, "未知"),
            total_quantity=float(r.total_quantity or 0),
            batch_count=r.batch_count,
            min_stock=float(r.min_stock) if r.min_stock else None,
            has_alert=float(r.min_stock or 0) > 0 and float(r.total_quantity or 0) < float(r.min_stock or 0),
        )
        for r in results
    ]


@router.put("/inventory/{inventory_id}", response_model=InventoryResponse, summary="更新库存记录")
def update_inventory(inventory_id: int, data: InventoryUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新库存记录的预警值、仓位、状态等"""
    inv = db.query(HerbInventory).filter(HerbInventory.id == inventory_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="库存记录不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(inv, key, value)
    db.commit()
    db.refresh(inv)
    resp = InventoryResponse.model_validate(inv)
    resp.herb_name = inv.herb.name if inv.herb else None
    return resp


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
    ref_inv = db.query(HerbInventory).filter(HerbInventory.herb_id == herb_id).first()
    ref_item = db.query(PrescriptionItem).filter(PrescriptionItem.herb_id == herb_id).first()
    if ref_inv or ref_item:
        herb.is_active = False
        db.commit()
        return {"deleted": False, "soft": True, "message": "存在库存/处方引用，已改为停用"}
    db.delete(herb)
    db.commit()
    return {"deleted": True, "soft": False, "message": "已删除"}