"""库存管理路由：物品 / 批次 / 流水 / 总览 / 预警 / 盘点

库存本质是关于"物品"的管理，中药只是物品的一种(item_type='中药'，可选关联 herbs 字典)。
耗材(针灸针/艾灸/外治)以相同结构管理，单位由 stock_items.unit 决定(g/盒/支/根/贴/包)。
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db, inventory_lock
from app.models.stock import StockItem, StockBatch, StockTransaction
from app.models.herb import Herb
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.stock import (
    StockItemCreate, StockItemUpdate, StockItemResponse,
    StockBatchIn, StockBatchOut, StockBatchResponse, StockBatchUpdate,
    StockTransactionResponse, StockOverview, StockAlert, StockCheckIn,
)

router = APIRouter(prefix="/stock", tags=["库存管理"])


def _batch_resp(b: StockBatch) -> StockBatchResponse:
    return StockBatchResponse(
        id=b.id, item_id=b.item_id, batch_number=b.batch_number, quantity=b.quantity,
        unit_price=b.unit_price, sale_price=b.sale_price, purchase_date=b.purchase_date,
        expiry_date=b.expiry_date, supplier=b.supplier, min_stock=b.min_stock,
        location=b.location, status=b.status, item_name=b.item.name, unit=b.item.unit,
        herb_id=b.item.herb_id,
    )


# ── 物品主数据 ──

@router.get("/items", response_model=list[StockItemResponse], summary="物品列表(药材/耗材)")
def list_items(
    item_type: str | None = Query(None, description="筛选类别"),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(StockItem)
    if item_type:
        q = q.filter(StockItem.item_type == item_type)
    if is_active is not None:
        q = q.filter(StockItem.is_active == is_active)
    items = q.all()
    if search:
        s = search.lower()
        items = [i for i in items if s in (i.name or "").lower() or s in (i.spec or "").lower()]
    items.sort(key=lambda i: (i.item_type, i.name or ""))
    ids = [i.id for i in items]
    totals: dict[int, float] = {}
    if ids:
        rows = db.query(
            StockBatch.item_id, func.sum(StockBatch.quantity)
        ).filter(
            StockBatch.item_id.in_(ids), StockBatch.status.in_(["正常", "近效期"])
        ).group_by(StockBatch.item_id).all()
        totals = {iid: float(tot or 0) for (iid, tot) in rows}
    return [
        StockItemResponse(
            id=i.id, item_type=i.item_type, name=i.name, spec=i.spec, unit=i.unit,
            sell_price=i.sell_price, herb_id=i.herb_id, min_stock=i.min_stock,
            is_active=i.is_active, total_quantity=totals.get(i.id, 0.0),
        ) for i in items
    ]


@router.post("/items", response_model=StockItemResponse, summary="新增物品(药材/耗材)")
def create_item(data: StockItemCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.herb_id:
        herb = db.query(Herb).filter(Herb.id == data.herb_id).first()
        if not herb:
            raise HTTPException(status_code=404, detail="关联药材不存在")
    item = StockItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return StockItemResponse(
        id=item.id, item_type=item.item_type, name=item.name, spec=item.spec, unit=item.unit,
        sell_price=item.sell_price, herb_id=item.herb_id, min_stock=item.min_stock,
        is_active=item.is_active, total_quantity=0.0,
    )


@router.put("/items/{item_id}", response_model=StockItemResponse, summary="更新物品")
def update_item(item_id: int, data: StockItemUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(StockItem).filter(StockItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    total = float(db.query(func.sum(StockBatch.quantity)).filter(
        StockBatch.item_id == item.id, StockBatch.status.in_(["正常", "近效期"])
    ).scalar() or 0)
    return StockItemResponse(
        id=item.id, item_type=item.item_type, name=item.name, spec=item.spec, unit=item.unit,
        sell_price=item.sell_price, herb_id=item.herb_id, min_stock=item.min_stock,
        is_active=item.is_active, total_quantity=total,
    )


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

@router.get("/batches", response_model=list[StockBatchResponse], summary="批次列表")
def list_batches(
    item_id: int | None = Query(None),
    herb_id: int | None = Query(None, description="按关联药材查(中药)"),
    status: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(StockBatch).join(StockItem, StockBatch.item_id == StockItem.id)
    if item_id:
        q = q.filter(StockBatch.item_id == item_id)
    if herb_id:
        q = q.filter(StockItem.herb_id == herb_id)
    if status:
        q = q.filter(StockBatch.status == status)
    batches = q.all()
    if search:
        s = search.lower()
        batches = [b for b in batches if s in (b.batch_number or "").lower() or s in (b.item.name or "").lower()]
    batches.sort(key=lambda b: (b.item.name or "", b.batch_number or ""))
    return [_batch_resp(b) for b in batches]


@router.post("/batches/in", response_model=StockBatchResponse, summary="入库(新增或累加批次)")
def batch_in(data: StockBatchIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(StockItem).filter(StockItem.id == data.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    batch_number = data.batch_number or date.today().strftime("%Y%m%d")
    exist = db.query(StockBatch).filter(
        StockBatch.item_id == data.item_id, StockBatch.batch_number == batch_number
    ).first()
    if exist:
        before = float(exist.quantity)
        exist.quantity = before + data.quantity
        batch = exist
        note_prefix = "入库累加"
    else:
        batch = StockBatch(
            item_id=data.item_id, batch_number=batch_number, quantity=data.quantity,
            unit_price=data.unit_price, sale_price=data.sale_price,
            purchase_date=data.purchase_date, expiry_date=data.expiry_date,
            supplier=data.supplier, min_stock=data.min_stock, location=data.location,
            status=data.status or "正常",
        )
        db.add(batch)
        before = 0.0
        note_prefix = "入库"
    db.flush()
    if data.sale_price is not None:
        item.sell_price = data.sale_price
    db.add(StockTransaction(
        item_id=data.item_id, batch_id=batch.id, transaction_type="入库", quantity=data.quantity,
        before_quantity=before, after_quantity=float(batch.quantity), reference_type="手动",
        operator=current_user.username, note=(data.note or note_prefix),
    ))
    db.commit()
    db.refresh(batch)
    return _batch_resp(batch)


@router.post("/batches/out", summary="出库(手动扣减, FIFO)")
def batch_out(data: StockBatchOut, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(StockItem).filter(StockItem.id == data.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    with inventory_lock:
        if data.batch_id:
            batch = db.query(StockBatch).filter(StockBatch.id == data.batch_id).with_for_update().first()
            if not batch or batch.item_id != data.item_id:
                raise HTTPException(status_code=400, detail="批次不存在或不属于该物品")
            avail = float(batch.quantity)
            if avail < data.quantity:
                raise HTTPException(status_code=400, detail=f"批次库存不足: 可用{avail}{item.unit}，需{data.quantity}{item.unit}")
            before = avail
            batch.quantity = avail - data.quantity
            db.add(StockTransaction(
                item_id=data.item_id, batch_id=batch.id, transaction_type="出库", quantity=data.quantity,
                before_quantity=before, after_quantity=float(batch.quantity), reference_type="手动",
                operator=current_user.username, note=data.note,
            ))
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
                b.quantity = float(b.quantity) - d
                remaining -= d
                db.add(StockTransaction(
                    item_id=data.item_id, batch_id=b.id, transaction_type="出库", quantity=d,
                    before_quantity=avail_total, after_quantity=avail_total - data.quantity,
                    reference_type="手动", operator=current_user.username, note=data.note,
                ))
        db.commit()
    return {"message": "出库成功", "quantity": data.quantity}


@router.put("/batches/{batch_id}", response_model=StockBatchResponse, summary="更新批次(纠错)")
def update_batch(batch_id: int, data: StockBatchUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.query(StockBatch).filter(StockBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")
    old_qty = float(batch.quantity)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(batch, key, value)
    if "sale_price" in payload and payload["sale_price"] is not None:
        item = db.query(StockItem).filter(StockItem.id == batch.item_id).first()
        if item:
            item.sell_price = payload["sale_price"]
    if "quantity" in payload and float(payload["quantity"]) != old_qty:
        db.add(StockTransaction(
            item_id=batch.item_id, batch_id=batch.id, transaction_type="调整",
            quantity=float(payload["quantity"]) - old_qty, before_quantity=old_qty,
            after_quantity=float(batch.quantity), reference_type="手动",
            operator=current_user.username, note="批次纠错调整",
        ))
    db.commit()
    db.refresh(batch)
    return _batch_resp(batch)


# ── 流水 ──

@router.get("/transactions", response_model=list[StockTransactionResponse], summary="出入库流水(入/出/余可追溯)")
def list_transactions(
    item_id: int | None = Query(None),
    transaction_type: str | None = Query(None),
    reference_type: str | None = Query(None),
    start: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
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
        q = q.filter(StockTransaction.created_at <= end + " 23:59:59")
    txns = q.order_by(StockTransaction.id.desc()).limit(limit).all()
    item_ids = {t.item_id for t in txns}
    names = {i.id: i.name for i in db.query(StockItem).filter(StockItem.id.in_(item_ids)).all()} if item_ids else {}
    names_unit = {i.id: i.unit for i in db.query(StockItem).filter(StockItem.id.in_(item_ids)).all()} if item_ids else {}
    batch_ids = {t.batch_id for t in txns if t.batch_id}
    bnos = {b.id: b.batch_number for b in db.query(StockBatch).filter(StockBatch.id.in_(batch_ids)).all()} if batch_ids else {}
    result = [
        StockTransactionResponse(
            id=t.id, item_id=t.item_id, item_name=names.get(t.item_id),
            unit=names_unit.get(t.item_id), batch_id=t.batch_id,
            batch_number=bnos.get(t.batch_id), transaction_type=t.transaction_type, quantity=t.quantity,
            before_quantity=t.before_quantity, after_quantity=t.after_quantity,
            reference_id=t.reference_id, reference_type=t.reference_type, operator=t.operator,
            note=t.note, created_at=t.created_at,
        ) for t in txns
    ]
    return result


# ── 总览 / 预警 ──

@router.get("/overview", response_model=list[StockOverview], summary="库存总览(按物品聚合)")
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
    rows = (
        db.query(StockBatch.item_id, func.sum(StockBatch.quantity), func.count(StockBatch.id))
        .filter(StockBatch.item_id.in_(ids), StockBatch.status.in_(["正常", "近效期"]))
        .group_by(StockBatch.item_id).all()
    ) if ids else []
    agg = {iid: (float(tot or 0), cnt) for (iid, tot, cnt) in rows}
    out = []
    for i in items:
        total, cnt = agg.get(i.id, (0.0, 0))
        threshold = float(i.min_stock or 0)
        has_alert = threshold > 0 and total < threshold
        out.append(StockOverview(
            item_id=i.id, item_name=i.name, item_type=i.item_type, unit=i.unit,
            total_quantity=total, batch_count=cnt, min_stock=i.min_stock, has_alert=has_alert,
        ))
    if alert_only:
        out = [o for o in out if o.has_alert]
    if search:
        s = search.lower()
        out = [o for o in out if s in o.item_name.lower()]
    out.sort(key=lambda o: o.item_name)
    return out


@router.get("/alerts", response_model=list[StockAlert], summary="库存预警(低于物品级阈值)")
def alerts(db: Session = Depends(get_db)):
    items = db.query(StockItem).filter(StockItem.is_active == True, StockItem.min_stock > 0).all()
    ids = [i.id for i in items]
    rows = (
        db.query(StockBatch.item_id, func.sum(StockBatch.quantity))
        .filter(StockBatch.item_id.in_(ids), StockBatch.status.in_(["正常", "近效期"]))
        .group_by(StockBatch.item_id).all()
    ) if ids else []
    totals = {r[0]: float(r[1] or 0) for r in rows}
    out = []
    for i in items:
        total = totals.get(i.id, 0.0)
        if total < float(i.min_stock or 0):
            out.append(StockAlert(
                item_id=i.id, item_name=i.name, unit=i.unit, current_quantity=total,
                min_stock=float(i.min_stock), alert_type="低于最低库存",
            ))
    return out


# ── 盘点 ──

@router.post("/check", summary="库房盘点(逐批次实盘调整, 可含损耗)")
def stock_check(data: StockCheckIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(StockItem).filter(StockItem.id == data.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    with inventory_lock:
        cur_total = float(
            db.query(func.sum(StockBatch.quantity)).filter(StockBatch.item_id == data.item_id).scalar() or 0
        )
        total_diff = 0.0
        for adj in data.adjustments:
            batch = db.query(StockBatch).filter(
                StockBatch.id == adj.batch_id, StockBatch.item_id == data.item_id
            ).with_for_update().first()
            if not batch:
                raise HTTPException(status_code=400, detail=f"批次不存在或不属于该物品: {adj.batch_id}")
            before = float(batch.quantity)
            diff = float(adj.counted) - before
            batch.quantity = float(adj.counted)
            total_diff += diff
            db.add(StockTransaction(
                item_id=data.item_id, batch_id=batch.id, transaction_type="盘点", quantity=diff,
                before_quantity=before, after_quantity=float(adj.counted), reference_type="盘点",
                operator=current_user.username, note=data.note or "盘点调整",
            ))
        db.commit()
    return {
        "message": "盘点完成", "item_id": data.item_id,
        "before_quantity": cur_total, "after_quantity": cur_total + total_diff,
    }
