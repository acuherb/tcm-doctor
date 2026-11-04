"""库存管理路由：物品 / 批次 / 流水 / 总览 / 预警 / 供应商 / 采购 / 报表 / 盘点

库存本质是关于"物品"的管理，中药只是物品的一种(item_type='中药'，可选关联 herbs 字典)。
耗材(针灸针/艾灸/外治)以相同结构管理，单位由 stock_items.unit 决定(g/盒/支/根/贴/包)。

进销存财务化：入库/出库/发药/损耗/盘点均向 StockTransaction 写入金额维度
(unit_cost / unit_price / cost_amount / revenue_amount)，使采购成本、COGS、收入、毛利可聚合。
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, case, and_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db, inventory_lock
from app.models.stock import (
    StockItem, StockBatch, StockTransaction, Supplier, PurchaseOrder, PurchaseItem, StockOption,
)
from app.models.herb import Herb
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.stock import (
    StockItemCreate, StockItemUpdate, StockItemResponse,
    StockBatchIn, StockBatchOut, StockBatchResponse, StockBatchUpdate,
    StockTransactionResponse, StockOverview, StockAlert, StockAdjustIn,
    SupplierCreate, SupplierUpdate, SupplierResponse,
    PurchaseOrderCreate, PurchaseOrderResponse, PurchaseItemResponse,
    ReportSummary, ReportProfitItem, ReportABCItem, ReportTurnover, SupplierPriceRow,
    StockOptionCreate, StockOptionUpdate, StockOptionResponse,
)

router = APIRouter(prefix="/stock", tags=["库存管理"])


def _gen_barcode(prefix: str, id_val: int) -> str:
    return f"{prefix}{id_val:08d}"


def _batch_resp(b: StockBatch) -> StockBatchResponse:
    return StockBatchResponse(
        id=b.id, item_id=b.item_id, batch_number=b.batch_number, quantity=b.quantity,
        unit_price=b.unit_price, purchase_date=b.purchase_date,
        expiry_date=b.expiry_date, supplier=b.supplier, supplier_id=b.supplier_id,
        min_stock=b.min_stock, location=b.location, status=b.status,
        barcode=b.barcode, item_name=b.item.name, unit=b.item.unit,
        herb_id=b.item.herb_id,
    )


def _item_base(item: StockItem, total: float, value: float) -> StockItemResponse:
    return StockItemResponse(
        id=item.id, item_type=item.item_type, name=item.name, spec=item.spec, unit=item.unit,
        sell_price=item.sell_price, herb_id=item.herb_id, min_stock=item.min_stock,
        is_active=item.is_active, barcode=item.barcode, default_supplier_id=item.default_supplier_id,
        total_quantity=total, stock_value=value,
    )


def _item_agg(db: Session, ids: list[int]) -> tuple[dict, dict]:
    """返回 {item_id: total_qty} 与 {item_id: stock_value}（仅正常/近效期批次计入）"""
    if not ids:
        return {}, {}
    rows = (
        db.query(
            StockBatch.item_id,
            func.sum(StockBatch.quantity),
            func.sum(StockBatch.quantity * func.coalesce(StockBatch.unit_price, 0)),
        )
        .filter(StockBatch.item_id.in_(ids), StockBatch.status.in_(["正常", "近效期"]))
        .group_by(StockBatch.item_id).all()
    )
    totals = {r[0]: float(r[1] or 0) for r in rows}
    values = {r[0]: float(r[2] or 0) for r in rows}
    return totals, values


# ── 物品主数据 ──

@router.get("/items", summary="物品列表(药材/耗材)")
def list_items(
    item_type: str | None = Query(None, description="筛选类别"),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(0, ge=0, description="0=返回全部(兼容下拉选择); >=1 时分页"),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(StockItem)
    if item_type:
        q = q.filter(StockItem.item_type == item_type)
    if is_active is not None:
        q = q.filter(StockItem.is_active == is_active)
    # 搜索下推到 SQL（名称/规格），避免全量捞出再内存过滤
    if search:
        s = f"%{search.strip()}%"
        q = q.filter(or_(StockItem.name.ilike(s), StockItem.spec.ilike(s)))
    q = q.order_by(StockItem.item_type, StockItem.name)
    if page and page > 0:
        total = q.count()
        rows = q.offset((page - 1) * page_size).limit(page_size).all()
        ids = [i.id for i in rows]
        totals, values = _item_agg(db, ids)
        return {
            "items": [_item_base(i, totals.get(i.id, 0.0), values.get(i.id, 0.0)) for i in rows],
            "total": total, "page": page, "page_size": page_size,
        }
    rows = q.all()
    ids = [i.id for i in rows]
    totals, values = _item_agg(db, ids)
    return [_item_base(i, totals.get(i.id, 0.0), values.get(i.id, 0.0)) for i in rows]


@router.post("/items", response_model=StockItemResponse, summary="新增物品(药材/耗材)")
def create_item(data: StockItemCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.herb_id:
        herb = db.query(Herb).filter(Herb.id == data.herb_id).first()
        if not herb:
            raise HTTPException(status_code=404, detail="关联药材不存在")
    item = StockItem(**data.model_dump())
    db.add(item)
    db.flush()
    if not item.barcode:
        item.barcode = _gen_barcode("IT", item.id)
    db.commit()
    db.refresh(item)
    return _item_base(item, 0.0, 0.0)


@router.put("/items/{item_id}", response_model=StockItemResponse, summary="更新物品")
def update_item(item_id: int, data: StockItemUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(StockItem).filter(StockItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    totals, values = _item_agg(db, [item.id])
    return _item_base(item, totals.get(item.id, 0.0), values.get(item.id, 0.0))


@router.delete("/items/{item_id}", summary="删除物品(同时删除其批次与流水)")
def delete_item(item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(StockItem).filter(StockItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    db.query(StockTransaction).filter(StockTransaction.item_id == item_id).delete()
    db.query(StockBatch).filter(StockBatch.item_id == item_id).delete()
    db.delete(item)
    db.commit()
    return {"deleted": item_id}


# ── 批次 ──

@router.get("/batches", summary="批次列表")
def list_batches(
    item_id: int | None = Query(None),
    herb_id: int | None = Query(None, description="按关联药材查(中药)"),
    status: str | None = Query(None),
    include_inactive: bool = Query(False, description="是否包含已停用(扣空)批次，默认隐藏"),
    search: str | None = Query(None),
    page: int = Query(0, ge=0, description="0=返回全部(兼容按物品查询); >=1 时分页"),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(StockBatch).join(StockItem, StockBatch.item_id == StockItem.id)
    if item_id is not None:
        q = q.filter(StockBatch.item_id == item_id)
    if herb_id is not None:
        q = q.filter(StockItem.herb_id == herb_id)
    if status is not None:
        q = q.filter(StockBatch.status == status)
    elif not include_inactive:
        q = q.filter(StockBatch.status != "停用")  # 默认隐藏扣空批次
    # 搜索下推到 SQL（批号/物品名），避免全量捞出再内存过滤
    if search:
        s = f"%{search.strip()}%"
        q = q.filter(or_(StockBatch.batch_number.ilike(s), StockItem.name.ilike(s)))
    q = q.order_by(StockItem.name, StockBatch.batch_number)

    def _build(rows):
        return [_batch_resp(b) for b in rows]

    if page and page > 0:
        total = q.count()
        rows = q.offset((page - 1) * page_size).limit(page_size).all()
        return {"items": _build(rows), "total": total, "page": page, "page_size": page_size}
    return _build(q.all())


def _do_inbound(db: Session, data: StockBatchIn, operator: str) -> StockBatch:
    """单物品入库核心(建/累加批次 + 入库流水)，不提交，由调用方统一 commit。"""
    item = db.query(StockItem).filter(StockItem.id == data.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    batch_number = data.batch_number or date.today().strftime("%Y%m%d")
    exist = db.query(StockBatch).filter(
        StockBatch.item_id == data.item_id, StockBatch.batch_number == batch_number
    ).first()
    uc = float(data.unit_price) if data.unit_price is not None else None
    if exist:
        before = float(exist.quantity)
        exist.quantity = before + data.quantity
        if uc is not None:
            exist.unit_price = uc
        if data.expiry_date:
            exist.expiry_date = data.expiry_date
        if data.supplier_id:
            exist.supplier_id = data.supplier_id
        if data.location:
            exist.location = data.location
        if data.status:
            exist.status = data.status
        batch = exist
        note_prefix = "入库累加"
    else:
        batch = StockBatch(
            item_id=data.item_id, batch_number=batch_number, quantity=data.quantity,
            unit_price=uc, purchase_date=data.purchase_date, expiry_date=data.expiry_date,
            supplier=data.supplier, supplier_id=data.supplier_id,
            min_stock=data.min_stock, location=data.location, status=data.status or "正常",
        )
        db.add(batch)
        before = 0.0
        note_prefix = "入库"
    db.flush()
    if not batch.barcode:
        batch.barcode = _gen_barcode("BA", batch.id)
    cost_amount = float(data.quantity) * uc if uc is not None else None
    db.add(StockTransaction(
        item_id=data.item_id, batch_id=batch.id, transaction_type="入库", quantity=data.quantity,
        before_quantity=before, after_quantity=float(batch.quantity),
        unit_cost=uc, cost_amount=cost_amount, revenue_amount=0.0,
        reference_type="手动", operator=operator, note=(data.note or note_prefix),
    ))
    return batch


@router.post("/batches/in", response_model=StockBatchResponse, summary="入库(新增或累加批次, 记录成本)")
def batch_in(data: StockBatchIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = _do_inbound(db, data, current_user.username)
    db.commit()
    db.refresh(batch)
    return _batch_resp(batch)


@router.post("/batches/in/bulk", summary="批量入库(多物品逐条建批次+流水)")
def batch_in_bulk(data: list[StockBatchIn], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    done = 0
    for entry in data:
        _do_inbound(db, entry, current_user.username)
        done += 1
    db.commit()
    return {"detail": f"已入库 {done} 项", "count": done}


def _apply_out(db, batch: StockBatch, qty: float, reference_type: str, reference_id, note, unit_price_sold=None):
    """通用出库/损耗扣减（带金额），返回是否扣空。"""
    uc = float(batch.unit_price) if batch.unit_price is not None else None
    before = float(batch.quantity)
    batch.quantity = before - qty
    depleted = False
    if batch.quantity <= 0:
        batch.quantity = 0.0
        batch.status = "停用"  # 扣空即自动停用, 列表默认隐藏
        depleted = True
    cost_amount = -(qty * uc) if uc is not None else None
    rev = (qty * float(unit_price_sold)) if unit_price_sold is not None else 0.0
    db.add(StockTransaction(
        item_id=batch.item_id, batch_id=batch.id, transaction_type=("出库" if reference_type != "损耗" else "损耗"),
        quantity=qty, before_quantity=before, after_quantity=float(batch.quantity),
        unit_cost=uc, unit_price=unit_price_sold, cost_amount=cost_amount,
        revenue_amount=rev,
        reference_id=reference_id, reference_type=reference_type,
        operator=note.get("operator"), note=note.get("note"),
    ))
    return depleted


@router.post("/batches/out", summary="出库(手动扣减, FIFO, 记录成本)")
def batch_out(data: StockBatchOut, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(StockItem).filter(StockItem.id == data.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    note_ctx = {"operator": current_user.username, "note": data.note}
    with inventory_lock:
        if data.batch_id:
            batch = db.query(StockBatch).filter(StockBatch.id == data.batch_id).with_for_update().first()
            if not batch or batch.item_id != data.item_id:
                raise HTTPException(status_code=400, detail="批次不存在或不属于该物品")
            avail = float(batch.quantity)
            if avail < data.quantity:
                raise HTTPException(status_code=400, detail=f"批次库存不足: 可用{avail}{item.unit}，需{data.quantity}{item.unit}")
            _apply_out(db, batch, data.quantity, "手动", None, note_ctx, unit_price_sold=data.unit_price)
        else:
            batches = db.query(StockBatch).filter(
                StockBatch.item_id == data.item_id, StockBatch.status.in_(["正常", "近效期"])
            ).with_for_update().order_by(StockBatch.id).all()
            avail_total = sum(float(b.quantity) for b in batches)
            if avail_total < data.quantity:
                raise HTTPException(status_code=400, detail=f"库存不足: 可用{avail_total}{item.unit}，需{data.quantity}{item.unit}")
            remaining = data.quantity
            for b in batches:
                if remaining <= 0:
                    break
                before_b = float(b.quantity)
                d = min(before_b, remaining)
                _apply_out(db, b, d, "手动", None, note_ctx, unit_price_sold=data.unit_price)
                remaining -= d
        db.commit()
    return {"message": "出库成功", "quantity": data.quantity}


@router.post("/batches/writeoff", summary="报损/核销(过期/变质损耗, 记录成本损失)")
def batch_writeoff(data: StockBatchOut, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """报损：与出库类似扣减批次，但 transaction_type=损耗，不计入收入（纯成本损失）。"""
    item = db.query(StockItem).filter(StockItem.id == data.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    note_ctx = {"operator": current_user.username, "note": (data.note or "报损/核销")}
    with inventory_lock:
        if data.batch_id:
            batch = db.query(StockBatch).filter(StockBatch.id == data.batch_id).with_for_update().first()
            if not batch or batch.item_id != data.item_id:
                raise HTTPException(status_code=400, detail="批次不存在或不属于该物品")
            if float(batch.quantity) < data.quantity:
                raise HTTPException(status_code=400, detail="批次库存不足")
            _apply_out(db, batch, data.quantity, "损耗", None, note_ctx)
        else:
            batches = db.query(StockBatch).filter(
                StockBatch.item_id == data.item_id, StockBatch.status.in_(["正常", "近效期"])
            ).with_for_update().order_by(StockBatch.id).all()
            avail_total = sum(float(b.quantity) for b in batches)
            if avail_total < data.quantity:
                raise HTTPException(status_code=400, detail=f"库存不足: 可用{avail_total}{item.unit}，需{data.quantity}{item.unit}")
            remaining = data.quantity
            for b in batches:
                if remaining <= 0:
                    break
                d = min(float(b.quantity), remaining)
                _apply_out(db, b, d, "损耗", None, note_ctx)
                remaining -= d
        db.commit()
    return {"message": "报损成功", "quantity": data.quantity}


@router.put("/batches/{batch_id}", response_model=StockBatchResponse, summary="更新批次(纠错)")
def update_batch(batch_id: int, data: StockBatchUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with inventory_lock:
        batch = db.query(StockBatch).filter(StockBatch.id == batch_id).with_for_update().first()
        if not batch:
            raise HTTPException(status_code=404, detail="批次不存在")
        old_qty = float(batch.quantity)
        payload = data.model_dump(exclude_unset=True)
        # 纠错不允许把库存改成负数：直接拒绝，避免流水 after_quantity 写负数导致数据不自洽
        if "quantity" in payload and float(payload["quantity"]) < 0:
            raise HTTPException(status_code=400, detail="批次数量不能为负")
        for key, value in payload.items():
            setattr(batch, key, value)
        if "quantity" in payload and float(batch.quantity) != old_qty:
            new_qty = float(batch.quantity)
            uc = float(batch.unit_price) if batch.unit_price is not None else None
            if new_qty <= 0:
                batch.quantity = 0.0
                batch.status = "停用"
            diff = new_qty - old_qty
            db.add(StockTransaction(
                item_id=batch.item_id, batch_id=batch.id, transaction_type="调整", quantity=diff,
                before_quantity=old_qty, after_quantity=float(batch.quantity),
                unit_cost=uc, cost_amount=(diff * uc) if uc is not None else None,
                revenue_amount=0.0, reference_type="手动",
                operator=current_user.username, note="批次纠错调整",
            ))
        db.commit()
    db.refresh(batch)
    return _batch_resp(batch)


# ── 流水 ──

@router.get("/transactions", summary="出入库流水(入/出/余/金额可追溯)")
def list_transactions(
    item_id: int | None = Query(None),
    transaction_type: str | None = Query(None),
    reference_type: str | None = Query(None),
    start: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end: str | None = Query(None),
    search: str | None = Query(None, description="按物品名称模糊搜索(下推 SQL)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(StockTransaction).join(
        StockItem, StockTransaction.item_id == StockItem.id
    ).outerjoin(StockBatch, StockTransaction.batch_id == StockBatch.id)
    if item_id:
        q = q.filter(StockTransaction.item_id == item_id)
    if transaction_type:
        q = q.filter(StockTransaction.transaction_type == transaction_type)
    if reference_type:
        q = q.filter(StockTransaction.reference_type == reference_type)
    if start:
        q = q.filter(StockTransaction.created_at >= start)
    if end:
        q = q.filter(StockTransaction.created_at <= end + " 23:59:59.999999")
    if search:
        s = f"%{search.strip()}%"
        q = q.filter(StockItem.name.ilike(s))
    total = q.count()
    txns = q.order_by(StockTransaction.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    item_ids = {t.item_id for t in txns}
    item_info = {i.id: (i.name, i.unit) for i in db.query(StockItem).filter(StockItem.id.in_(item_ids)).all()} if item_ids else {}
    batch_ids = {t.batch_id for t in txns if t.batch_id}
    bnos = {b.id: b.batch_number for b in db.query(StockBatch).filter(StockBatch.id.in_(batch_ids)).all()} if batch_ids else {}
    items = [
        StockTransactionResponse(
            id=t.id, item_id=t.item_id, item_name=item_info.get(t.item_id, ("", ""))[0], unit=item_info.get(t.item_id, ("", ""))[1],
            batch_id=t.batch_id, batch_number=bnos.get(t.batch_id), transaction_type=t.transaction_type,
            quantity=t.quantity, before_quantity=t.before_quantity, after_quantity=t.after_quantity,
            unit_cost=t.unit_cost, unit_price=t.unit_price, cost_amount=t.cost_amount,
            revenue_amount=t.revenue_amount, reference_id=t.reference_id, reference_type=t.reference_type,
            operator=t.operator, note=t.note, created_at=t.created_at,
        ) for t in txns
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ── 总览 / 预警 ──

@router.get("/overview", response_model=list[StockOverview], summary="库存总览(按物品聚合, 含库存金额)")
def overview(
    item_type: str | None = Query(None),
    search: str | None = Query(None),
    alert_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    q = db.query(StockItem).filter(StockItem.is_active == True)
    if item_type:
        q = q.filter(StockItem.item_type == item_type)
    items = q.all()
    ids = [i.id for i in items]
    totals, values = _item_agg(db, ids)
    out = []
    for i in items:
        total = totals.get(i.id, 0.0)
        value = values.get(i.id, 0.0)
        threshold = float(i.min_stock or 0)
        has_alert = threshold > 0 and total < threshold
        out.append(StockOverview(
            item_id=i.id, item_name=i.name, item_type=i.item_type, unit=i.unit,
            total_quantity=total, batch_count=0, min_stock=i.min_stock,
            has_alert=has_alert, stock_value=value,
        ))
    # batch_count 单独统计（含正常/近效期）
    if ids:
        bc = dict(db.query(StockBatch.item_id, func.count(StockBatch.id)).filter(
            StockBatch.item_id.in_(ids), StockBatch.status.in_(["正常", "近效期"])
        ).group_by(StockBatch.item_id).all())
        for o in out:
            o.batch_count = bc.get(o.item_id, 0)
    if alert_only:
        out = [o for o in out if o.has_alert]
    if search:
        s = search.lower()
        out = [o for o in out if s in o.item_name.lower()]
    out.sort(key=lambda o: o.item_name)
    return out


@router.get("/alerts", response_model=list[StockAlert], summary="多维库存预警(低库存/近效期/呆滞/高价值积压)")
def alerts(
    db: Session = Depends(get_db),
    include_low: bool = Query(True),
    include_expiry: bool = Query(True),
    expiry_days: int = Query(90, description="近效期提前天数"),
    include_stagnant: bool = Query(True),
    stagnant_days: int = Query(180, description="呆滞阈值(天无出入)"),
    include_highvalue: bool = Query(True),
    highvalue_threshold: float = Query(5000.0, description="高价值积压阈值(金额)"),
):
    items = db.query(StockItem).filter(StockItem.is_active == True).all()
    ids = [i.id for i in items]
    totals, values = _item_agg(db, ids)
    today = date.today()
    out: list[StockAlert] = []

    # 低库存
    if include_low:
        for i in items:
            t = totals.get(i.id, 0.0)
            if i.min_stock and t < float(i.min_stock):
                out.append(StockAlert(item_id=i.id, item_name=i.name, item_type=i.item_type, unit=i.unit,
                                     current_quantity=t, min_stock=float(i.min_stock),
                                     alert_type="低于最低库存", stock_value=values.get(i.id, 0.0)))

    # 近效期（取最早效期的在库批次）
    if include_expiry:
        exp_rows = (
            db.query(StockBatch.item_id, StockBatch.expiry_date, StockBatch.quantity)
            .filter(StockBatch.item_id.in_(ids), StockBatch.status.in_(["正常", "近效期"]),
                    StockBatch.expiry_date.isnot(None), StockBatch.quantity > 0)
            .all()
        ) if ids else []
        by_item: dict[int, tuple[str, int]] = {}
        for item_id, exp, qty in exp_rows:
            try:
                d = datetime.strptime(exp, "%Y-%m-%d").date()
            except Exception:
                continue
            left = (d - today).days
            if 0 <= left <= expiry_days:
                if item_id not in by_item or d < datetime.strptime(by_item[item_id][0], "%Y-%m-%d").date():
                    by_item[item_id] = (exp, left)
        for item_id, (exp, left) in by_item.items():
            i = next(x for x in items if x.id == item_id)
            out.append(StockAlert(item_id=item_id, item_name=i.name, item_type=i.item_type, unit=i.unit,
                                 current_quantity=totals.get(item_id, 0.0), min_stock=i.min_stock,
                                 alert_type="近效期", expiry_date=exp, days_to_expiry=left,
                                 stock_value=values.get(item_id, 0.0)))

    # 呆滞（最近一次流水距今超过阈值且无出库）
    if include_stagnant:
        last_txn = (
            db.query(StockTransaction.item_id, func.max(StockTransaction.created_at))
            .filter(StockTransaction.item_id.in_(ids)).group_by(StockTransaction.item_id).all()
        ) if ids else []
        last_map = {r[0]: r[1] for r in last_txn}
        for i in items:
            t = totals.get(i.id, 0.0)
            if t <= 0:
                continue
            lt = last_map.get(i.id)
            last_days = (datetime.now() - lt).days if lt else 9999
            if last_days >= stagnant_days:
                out.append(StockAlert(item_id=i.id, item_name=i.name, item_type=i.item_type, unit=i.unit,
                                     current_quantity=t, min_stock=i.min_stock,
                                     alert_type="呆滞", last_move_days=last_days,
                                     stock_value=values.get(i.id, 0.0)))

    # 高价值积压
    if include_highvalue:
        for i in items:
            v = values.get(i.id, 0.0)
            if v >= highvalue_threshold and totals.get(i.id, 0.0) > 0:
                out.append(StockAlert(item_id=i.id, item_name=i.name, item_type=i.item_type, unit=i.unit,
                                     current_quantity=totals.get(i.id, 0.0), min_stock=i.min_stock,
                                     alert_type="高价值积压", stock_value=v))

    return out


# ── 盘点 ──

def _weighted_avg_cost(batches: list) -> float | None:
    tot_q = 0.0
    tot_c = 0.0
    for b in batches:
        q = float(b.quantity or 0)
        uc = float(b.unit_price) if b.unit_price is not None else None
        if uc is not None and q > 0:
            tot_q += q
            tot_c += q * uc
    return (tot_c / tot_q) if tot_q > 0 else None


@router.post("/adjust/bulk", summary="批量盘点校准(按物品实盘总数, 自动 FIFO 调账)")
def adjust_bulk(data: list[StockAdjustIn], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """对每个物品按实盘总数校准：盘盈(实盘>当前)新增一个批次(取加权平均成本)，
    盘亏(实盘<当前)按 FIFO 扣减批次；均记 transaction_type=盘点 的流水。
    delta≈0 的物品自动跳过。后台仍保留批次(成本/效期)记录，但操作层面不暴露批次。"""
    operator = current_user.username
    done = 0
    with inventory_lock:
        for entry in data:
            item = db.query(StockItem).filter(StockItem.id == entry.item_id).first()
            if not item:
                continue
            batches = db.query(StockBatch).filter(
                StockBatch.item_id == entry.item_id
            ).order_by(StockBatch.id).with_for_update().all()
            current = float(sum((b.quantity or 0) for b in batches))
            delta = float(entry.counted) - current
            if abs(delta) < 1e-9:
                continue
            note = entry.note or "批量盘点调整"
            if delta > 0:
                avg = _weighted_avg_cost(batches)
                batch = StockBatch(
                    item_id=entry.item_id,
                    batch_number=date.today().strftime("%Y%m%d") + "-PD",
                    quantity=delta, unit_price=avg, status="正常",
                )
                db.add(batch)
                db.flush()
                if not batch.barcode:
                    batch.barcode = _gen_barcode("BA", batch.id)
                cost_amount = delta * avg if avg is not None else None
                db.add(StockTransaction(
                    item_id=entry.item_id, batch_id=batch.id, transaction_type="盘点", quantity=delta,
                    before_quantity=current, after_quantity=current + delta,
                    unit_cost=avg, cost_amount=cost_amount, revenue_amount=0.0,
                    reference_type="盘点", operator=operator, note=note,
                ))
            else:
                remain = -delta
                for b in batches:
                    if remain <= 0:
                        break
                    take = min(float(b.quantity or 0), remain)
                    if take <= 0:
                        continue
                    before = float(b.quantity)
                    b.quantity = before - take
                    if b.quantity <= 0:
                        b.quantity = 0.0
                        b.status = "停用"
                    remain -= take
                    uc = float(b.unit_price) if b.unit_price is not None else None
                    db.add(StockTransaction(
                        item_id=entry.item_id, batch_id=b.id, transaction_type="盘点", quantity=-take,
                        before_quantity=before, after_quantity=float(b.quantity),
                        unit_cost=uc, cost_amount=-(take * uc) if uc is not None else None,
                        revenue_amount=0.0, reference_type="盘点", operator=operator, note=note,
                    ))
            done += 1
        db.commit()
    return {"detail": f"已盘点 {done} 项", "count": done}


# ── 供应商 ──

@router.get("/suppliers", response_model=list[SupplierResponse], summary="供应商列表")
def list_suppliers(is_active: bool | None = Query(None), search: str | None = Query(None), db: Session = Depends(get_db)):
    q = db.query(Supplier)
    if is_active is not None:
        q = q.filter(Supplier.is_active == is_active)
    sups = q.all()
    if search:
        s = search.lower()
        sups = [x for x in sups if s in x.name.lower() or s in (x.contact or "").lower()]
    return sups


@router.post("/suppliers", response_model=SupplierResponse, summary="新增供应商")
def create_supplier(data: SupplierCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sup = Supplier(**data.model_dump())
    db.add(sup)
    db.commit()
    db.refresh(sup)
    return sup


@router.put("/suppliers/{sid}", response_model=SupplierResponse, summary="更新供应商")
def update_supplier(sid: int, data: SupplierUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sup = db.query(Supplier).filter(Supplier.id == sid).first()
    if not sup:
        raise HTTPException(status_code=404, detail="供应商不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(sup, key, value)
    db.commit()
    db.refresh(sup)
    return sup


@router.delete("/suppliers/{sid}", summary="删除供应商")
def delete_supplier(sid: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sup = db.query(Supplier).filter(Supplier.id == sid).first()
    if not sup:
        raise HTTPException(status_code=404, detail="供应商不存在")
    if db.query(StockBatch).filter(StockBatch.supplier_id == sid).first():
        raise HTTPException(status_code=400, detail="该供应商已有进货批次，无法删除")
    if db.query(StockItem).filter(StockItem.default_supplier_id == sid).first():
        raise HTTPException(status_code=400, detail="该供应商被某些物品设为默认供应商，无法删除")
    if db.query(PurchaseOrder).filter(PurchaseOrder.supplier_id == sid).first():
        raise HTTPException(status_code=400, detail="该供应商已有采购单记录，无法删除")
    db.delete(sup)
    db.commit()
    return {"deleted": sid}


# ── 采购入库 ──

def _po_resp(po: PurchaseOrder) -> PurchaseOrderResponse:
    return PurchaseOrderResponse(
        id=po.id, order_no=po.order_no, supplier_id=po.supplier_id, supplier_name=po.supplier_name,
        order_date=po.order_date, note=po.note, status=po.status, total_amount=float(po.total_amount or 0),
        operator=po.operator, created_at=po.created_at,
        items=[PurchaseItemResponse(
            id=it.id, item_id=it.item_id, item_name=None,
            batch_number=it.batch_number, quantity=it.quantity, unit_price=it.unit_price,
            amount=it.amount, expiry_date=it.expiry_date, location=it.location,
        ) for it in po.items],
    )


@router.post("/purchases", response_model=PurchaseOrderResponse, summary="采购入库(生成批次与入库流水)")
def create_purchase(data: PurchaseOrderCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == data.supplier_id).first() if data.supplier_id else None
    if data.supplier_id and not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    order_no = "PO" + datetime.now().strftime("%Y%m%d%H%M%S")
    po = PurchaseOrder(
        order_no=order_no, supplier_id=data.supplier_id, supplier_name=supplier.name if supplier else None,
        order_date=data.order_date or date.today().strftime("%Y-%m-%d"), note=data.note,
        status="已入库", operator=current_user.username, total_amount=0.0,
    )
    db.add(po)
    db.flush()
    total = 0.0
    item_names = {i.id: i.name for i in db.query(StockItem).all()}
    for it in data.items:
        item = db.query(StockItem).filter(StockItem.id == it.item_id).first()
        if not item:
            raise HTTPException(status_code=400, detail=f"物品不存在: {it.item_id}")
        amount = float(it.quantity) * float(it.unit_price)
        total += amount
        bn = it.batch_number or date.today().strftime("%Y%m%d")
        batch = db.query(StockBatch).filter(
            StockBatch.item_id == it.item_id, StockBatch.batch_number == bn
        ).with_for_update().first()
        if batch:
            before = float(batch.quantity)
            batch.quantity = before + it.quantity
            batch.unit_price = it.unit_price
            if it.expiry_date:
                batch.expiry_date = it.expiry_date
            if it.location:
                batch.location = it.location
        else:
            before = 0.0
            batch = StockBatch(
                item_id=it.item_id, batch_number=bn, quantity=it.quantity, unit_price=it.unit_price,
                purchase_date=po.order_date, expiry_date=it.expiry_date,
                supplier=supplier.name if supplier else None, supplier_id=data.supplier_id,
                location=it.location, status="正常",
            )
            db.add(batch)
            db.flush()
        if not batch.barcode:
            batch.barcode = _gen_barcode("BA", batch.id)
        db.add(StockTransaction(
            item_id=it.item_id, batch_id=batch.id, transaction_type="入库", quantity=it.quantity,
            before_quantity=(before if batch.quantity else 0.0),
            after_quantity=float(batch.quantity), unit_cost=it.unit_price,
            cost_amount=amount, revenue_amount=0.0, reference_id=po.id, reference_type="采购",
            operator=current_user.username, note=f"采购单{order_no}",
        ))
        db.add(PurchaseItem(
            po_id=po.id, item_id=it.item_id, batch_number=batch.batch_number, quantity=it.quantity,
            unit_price=it.unit_price, amount=amount, expiry_date=it.expiry_date, location=it.location,
        ))
    po.total_amount = total
    db.commit()
    db.refresh(po)
    # 重新构造响应（含物品名）
    resp = _po_resp(po)
    for r, it in zip(resp.items, po.items):
        r.item_name = item_names.get(it.item_id)
    return resp


@router.get("/purchases", summary="采购单列表")
def list_purchases(
    page: int = Query(0, ge=0, description="0=返回全部(兼容下拉选择); >=1 时分页"),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    # joinedload 预载明细，消除逐单懒加载的 N+1
    q = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).order_by(PurchaseOrder.id.desc())
    item_names = {i.id: i.name for i in db.query(StockItem).all()}

    def _build(pos):
        result = []
        for po in pos:
            r = _po_resp(po)
            for it in r.items:
                it.item_name = item_names.get(it.item_id)
            result.append(r)
        return result

    if page and page > 0:
        total = q.count()
        pos = q.offset((page - 1) * page_size).limit(page_size).all()
        return {"items": _build(pos), "total": total, "page": page, "page_size": page_size}
    return _build(q.all())


# ── 条码查询 ──

@router.get("/lookup", summary="按条码查询物品或批次")
def lookup(barcode: str = Query(...), db: Session = Depends(get_db)):
    item = db.query(StockItem).filter(StockItem.barcode == barcode).first()
    if item:
        totals, values = _item_agg(db, [item.id])
        return {"type": "item", "data": _item_base(item, totals.get(item.id, 0.0), values.get(item.id, 0.0))}
    batch = db.query(StockBatch).filter(StockBatch.barcode == barcode).first()
    if batch:
        return {"type": "batch", "data": _batch_resp(batch)}
    raise HTTPException(status_code=404, detail="未找到该条码对应的物品或批次")


# ── 报表 ──

@router.get("/report/summary", response_model=ReportSummary, summary="进销存汇总(期间采购成本/收入/COGS/毛利/期末库存)")
def report_summary(
    start: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
):
    base = db.query(StockTransaction)
    if start:
        base = base.filter(StockTransaction.created_at >= start)
    if end:
        base = base.filter(StockTransaction.created_at <= end + " 23:59:59.999999")
    # 用 SQL 聚合替代全量 q.all() 后在内存 sum（避免流水增长后的内存压力）
    pc, cg, rev = base.with_entities(
        # 采购成本：仅『入库』（冲红非采购，不计入）
        func.coalesce(func.sum(case((StockTransaction.transaction_type == "入库", StockTransaction.cost_amount), else_=0)), 0),
        # COGS：『出库』销售成本 + 『冲红』退回成本抵消（冲红 cost_amount>0 表示货退回，减少 COGS）
        func.coalesce(func.sum(case(
            (or_(and_(StockTransaction.transaction_type == "出库", StockTransaction.cost_amount < 0),
                 and_(StockTransaction.transaction_type == "冲红", StockTransaction.cost_amount > 0)),
             -StockTransaction.cost_amount), else_=0)), 0),
        # 收入：『出库』正收入 + 『冲红』退款(revenue_amount<0)抵消
        func.coalesce(func.sum(case(
            (or_(and_(StockTransaction.transaction_type == "出库", StockTransaction.revenue_amount > 0),
                 and_(StockTransaction.transaction_type == "冲红", StockTransaction.revenue_amount != 0)),
             StockTransaction.revenue_amount), else_=0)), 0),
    ).first()
    purchase_cost = 0.0 if pc is None else float(pc)
    # COGS 仅统计「出库」（销售/手动出库的成本）；损耗/盘点/调整的成本不并入销售成本，避免毛利被系统性低估
    cogs = 0.0 if cg is None else float(cg)
    sales_revenue = 0.0 if rev is None else float(rev)
    gross_profit = sales_revenue - cogs
    gross_margin = (gross_profit / sales_revenue) if sales_revenue else 0.0
    ending_inventory_value = float(
        db.query(func.sum(StockBatch.quantity * func.coalesce(StockBatch.unit_price, 0))).scalar() or 0
    )
    return ReportSummary(
        period_start=start, period_end=end, purchase_cost=purchase_cost, sales_revenue=sales_revenue,
        cogs=cogs, gross_profit=gross_profit, gross_margin=gross_margin,
        ending_inventory_value=ending_inventory_value,
    )


@router.get("/report/profit", response_model=list[ReportProfitItem], summary="毛利明细(按物品)")
def report_profit(
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
):
    base = db.query(StockTransaction)
    if start:
        base = base.filter(StockTransaction.created_at >= start)
    if end:
        base = base.filter(StockTransaction.created_at <= end + " 23:59:59.999999")
    # 按物品 SQL 分组聚合，替代全量拉取后在内存循环
    rows = base.with_entities(
        StockTransaction.item_id,
        # 收入：出库正收入 + 冲红退款抵消
        func.coalesce(func.sum(case(
            (or_(and_(StockTransaction.transaction_type == "出库", StockTransaction.revenue_amount > 0),
                 and_(StockTransaction.transaction_type == "冲红", StockTransaction.revenue_amount != 0)),
             StockTransaction.revenue_amount), else_=0)), 0),
        # COGS：出库销售成本 + 冲红退回成本抵消
        func.coalesce(func.sum(case(
            (or_(and_(StockTransaction.transaction_type == "出库", StockTransaction.cost_amount < 0),
                 and_(StockTransaction.transaction_type == "冲红", StockTransaction.cost_amount > 0)),
             -StockTransaction.cost_amount), else_=0)), 0),
    ).group_by(StockTransaction.item_id).all()
    names = {i.id: (i.name, i.unit) for i in db.query(StockItem).all()}
    out = []
    for item_id, rev, cogs in rows:
        rev = 0.0 if rev is None else float(rev)
        # COGS 仅算出库成本（排除损耗/盘点/调整），与 summary 口径一致
        cogs = 0.0 if cogs is None else float(cogs)
        gp = rev - cogs
        name, unit = names.get(item_id, (str(item_id), ""))
        out.append(ReportProfitItem(
            item_id=item_id, item_name=name, unit=unit, revenue=rev, cogs=cogs,
            gross_profit=gp, gross_margin=(gp / rev) if rev else 0.0,
        ))
    out.sort(key=lambda x: x.gross_profit, reverse=True)
    return out


@router.get("/report/abc", response_model=list[ReportABCItem], summary="ABC 分类(按库存金额)")
def report_abc(db: Session = Depends(get_db)):
    items = db.query(StockItem).filter(StockItem.is_active == True).all()
    ids = [i.id for i in items]
    _, values = _item_agg(db, ids)
    rows = sorted([(i, values.get(i.id, 0.0)) for i in items], key=lambda x: x[1], reverse=True)
    total_value = sum(v for _, v in rows) or 1.0
    cum = 0.0
    out = []
    for i, v in rows:
        ratio = v / total_value
        cum += ratio
        cat = "A" if cum <= 0.7 else ("B" if cum <= 0.9 else "C")
        out.append(ReportABCItem(item_id=i.id, item_name=i.name, unit=i.unit, stock_value=v,
                                value_ratio=ratio, cumulative_ratio=cum, category=cat))
    return out


@router.get("/report/turnover", response_model=list[ReportTurnover], summary="周转率(期间COGS/平均库存金额)")
def report_turnover(
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
):
    base = db.query(StockTransaction)
    if start:
        base = base.filter(StockTransaction.created_at >= start)
    if end:
        base = base.filter(StockTransaction.created_at <= end + " 23:59:59.999999")
    # 按物品 SQL 分组聚合净金额变动（入库正、出/损/盘点/调整负）与 COGS（仅出库），
    # 替代全量拉取后在内存循环
    rows = base.with_entities(
        StockTransaction.item_id,
        # 净金额变动（入库正、出/损/盘点/调整/冲红负），冲红的正 cost_amount 表示货退回、库存回升
        func.coalesce(func.sum(StockTransaction.cost_amount), 0),
        # COGS：出库销售成本 + 冲红退回成本抵消
        func.coalesce(func.sum(case(
            (or_(and_(StockTransaction.transaction_type == "出库", StockTransaction.cost_amount < 0),
                 and_(StockTransaction.transaction_type == "冲红", StockTransaction.cost_amount > 0)),
             -StockTransaction.cost_amount), else_=0)), 0),
    ).group_by(StockTransaction.item_id).all()
    net_change_map = {item_id: (0.0 if nc is None else float(nc)) for item_id, nc, _ in rows}
    cogs_map = {item_id: (0.0 if cg is None else float(cg)) for item_id, _, cg in rows}
    names = {i.id: (i.name, i.unit) for i in db.query(StockItem).all()}
    # 期末各物品库存金额（按 item_id 分别算，含所有批次；停用批次数量为 0 不影响）
    item_ending = dict(
        db.query(StockBatch.item_id, func.sum(StockBatch.quantity * func.coalesce(StockBatch.unit_price, 0)))
        .group_by(StockBatch.item_id).all()
    ) if rows else {}
    out = []
    for item_id, cogs in cogs_map.items():
        ending_val = float(item_ending.get(item_id, 0.0) or 0)
        beginning_val = ending_val - net_change_map.get(item_id, 0.0)  # 期初 = 期末 - 期间净变动
        avg = (beginning_val + ending_val) / 2
        turn = cogs / avg if avg > 0 else 0.0
        name, unit = names.get(item_id, (str(item_id), ""))
        out.append(ReportTurnover(item_id=item_id, item_name=name, unit=unit, cogs=cogs,
                                 avg_inventory_value=avg, turnover=turn))
    out.sort(key=lambda x: x.turnover, reverse=True)
    return out


@router.get("/report/supplier-price", response_model=list[SupplierPriceRow], summary="供应商比价(同物品不同批次进价)")
def report_supplier_price(db: Session = Depends(get_db)):
    batches = db.query(StockBatch).filter(StockBatch.supplier_id.isnot(None), StockBatch.quantity > 0).all()
    names = {i.id: (i.name, i.unit) for i in db.query(StockItem).all()}
    suppliers = {s.id: s.name for s in db.query(Supplier).all()}
    agg: dict[tuple, dict] = {}
    for b in batches:
        if b.unit_price is None:
            continue
        key = (b.item_id, b.supplier_id)
        a = agg.setdefault(key, {"min": b.unit_price, "max": b.unit_price, "sum": b.unit_price, "n": 1, "last": b.unit_price})
        a["min"] = min(a["min"], b.unit_price)
        a["max"] = max(a["max"], b.unit_price)
        a["sum"] += b.unit_price
        a["n"] += 1
        a["last"] = b.unit_price
    out = []
    for (item_id, sid), a in agg.items():
        name, unit = names.get(item_id, (str(item_id), ""))
        out.append(SupplierPriceRow(
            item_id=item_id, item_name=name, unit=unit, supplier_name=suppliers.get(sid, str(sid)),
            min_cost=a["min"], max_cost=a["max"], avg_cost=a["sum"] / a["n"], last_cost=a["last"],
        ))
    out.sort(key=lambda x: (x.item_name, x.supplier_name))
    return out


# ── 库存选项(类别/单位) ──
# 受控词表：物品类别与计量单位从硬编码/自由文本改为可在「库存选项」界面维护，
# 新增类别(如'理疗耗材')或单位不再需要改代码。

@router.get("/options", summary="库存选项列表(类别/单位)")
def list_options(
    opt_type: str | None = Query(None, pattern="^(category|unit)$"),
    db: Session = Depends(get_db),
):
    q = db.query(StockOption)
    if opt_type:
        q = q.filter(StockOption.opt_type == opt_type)
    opts = q.order_by(StockOption.opt_type, StockOption.id).all()
    return [StockOptionResponse.model_validate(o) for o in opts]


@router.post("/options", response_model=StockOptionResponse, status_code=201, summary="新增库存选项")
def create_option(
    data: StockOptionCreate,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.query(StockOption).filter(StockOption.opt_type == data.opt_type, StockOption.name == data.name).first():
        raise HTTPException(status_code=400, detail=f"选项「{data.name}」已存在")
    opt = StockOption(opt_type=data.opt_type, name=data.name, color=data.color, is_active=data.is_active)
    db.add(opt)
    db.commit()
    db.refresh(opt)
    return opt


@router.put("/options/{opt_id}", response_model=StockOptionResponse, summary="更新库存选项")
def update_option(
    opt_id: int,
    data: StockOptionUpdate,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opt = db.get(StockOption, opt_id)
    if not opt:
        raise HTTPException(status_code=404, detail="选项不存在")
    if data.opt_type is not None:
        opt.opt_type = data.opt_type
    if data.name is not None:
        if db.query(StockOption).filter(
            StockOption.opt_type == opt.opt_type, StockOption.name == data.name, StockOption.id != opt_id
        ).first():
            raise HTTPException(status_code=400, detail=f"选项「{data.name}」已存在")
        # 类别改名须同步已归该类的物品：item_type 存的是类别名而非外键，
        # 不同步会导致物品管理按新类别筛选时查不到数据，只能逐条手改。
        if opt.opt_type == "category" and opt.name != data.name:
            db.query(StockItem).filter(StockItem.item_type == opt.name).update(
                {StockItem.item_type: data.name}, synchronize_session=False
            )
        opt.name = data.name
    if "color" in data.model_fields_set:
        opt.color = data.color
    if data.is_active is not None:
        opt.is_active = data.is_active
    db.commit()
    db.refresh(opt)
    return opt


@router.delete("/options/{opt_id}", summary="删除库存选项")
def delete_option(
    opt_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opt = db.get(StockOption, opt_id)
    if not opt:
        raise HTTPException(status_code=404, detail="选项不存在")
    # 类别仍被物品引用时拒绝删除：item_type 是名称字段，删掉类别会让这些物品
    # 在下拉里无对应项、按类别筛选也永远查不到，数据将变成"孤儿"。
    if opt.opt_type == "category":
        used = db.query(StockItem).filter(StockItem.item_type == opt.name).count()
        if used:
            raise HTTPException(
                status_code=400,
                detail=f"类别「{opt.name}」下仍有 {used} 个物品，请先改名或调整这些物品的类别后再删除",
            )
    db.delete(opt)
    db.commit()
    return {"detail": "已删除"}