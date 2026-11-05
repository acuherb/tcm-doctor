"""收费管理路由：开方后生成收费单、收款、退费、收据与统计。

与库存/发药解耦：本域只管「钱」的闭环；库存扣减仍在「发药」环节完成。
权限由网关中间件按 /billing 域放行（billing:read / billing:write），此处仅取当前收银员信息。
"""
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.billing import Charge, _to_decimal
from app.models.prescription import Prescription
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.billing import (
    ChargeCreate, ChargeResponse, ChargeDetailResponse, ChargeListResponse,
    PayRequest, RefundRequest, CancelRequest,
)
from app.schemas.prescription import PrescriptionResponse
from app.services.billing_service import (
    create_charge as create_charge_service,
    apply_payment, refund_charge_record, cancel_charge_record,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["收费管理"])


def _charge_to_response(c: Charge) -> ChargeResponse:
    return ChargeResponse.model_validate(c)


def _transition(db: Session, charge_id: int, expected: str, new: str) -> None:
    """条件 UPDATE 原子占用状态：并发下只有一个请求能把旧状态改成新状态。

    取代「读状态 → 判断 → 写」的 TOCTOU 模式；失败即回滚并提示刷新，天然幂等。
    """
    # 用原生 SQL 绕过 ORM identity map，避免 Query.update() 触发 autoflush
    # 把服务层刚设好的内存状态提前写回，导致 WHERE 条件失配。
    # no_autoflush：服务层已把新状态设在 ORM 对象上，若此刻被 autoflush 提前写回，
    # WHERE status = expected 就会失配。显式禁用，不依赖 Session 全局配置。
    with db.no_autoflush:
        n = db.execute(
            text("UPDATE charges SET status = :new WHERE id = :id AND status = :expected"),
            {"new": new, "id": charge_id, "expected": expected},
        ).rowcount
    if n != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"收费单状态已变更（需为「{expected}」），请刷新后重试",
        )


@router.post("/charges", response_model=ChargeResponse, summary="开具收费单（可同时收款）")
def create_charge(
    payload: ChargeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """为处方生成收费单（prescription_id 给定）；或创建非处方收费（如挂号费，prescription_id 留空）。

    传入收款方式与实收金额则直接置为「已收费」。同一处方已有「待收费」单时复用，避免重复开单。
    """
    charge = create_charge_service(db, payload, current_user)
    return _charge_to_response(charge)


@router.get("/charges", response_model=ChargeListResponse, summary="收费单列表（筛选+分页）")
def list_charges(
    prescription_id: int | None = Query(None),
    patient_id: int | None = Query(None),
    patient_name: str | None = Query(None, description="患者姓名模糊匹配"),
    status: str | None = Query(None),
    kind: str | None = Query(None, description="收费类型: prescription/registration"),
    start_date: str | None = Query(None, description="创建日期起 yyyy-mm-dd"),
    end_date: str | None = Query(None, description="创建日期止 yyyy-mm-dd"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Charge)
    if prescription_id is not None:
        q = q.filter(Charge.prescription_id == prescription_id)
    if patient_id is not None:
        q = q.filter(Charge.patient_id == patient_id)
    if kind:
        q = q.filter(Charge.kind == kind)
    if patient_name:
        q = q.filter(Charge.patient_name.contains(patient_name))
    if status:
        q = q.filter(Charge.status == status)
    if start_date:
        q = q.filter(Charge.created_at >= start_date)
    if end_date:
        q = q.filter(Charge.created_at < end_date + " 23:59:59")
    total = q.count()
    items = (
        q.order_by(Charge.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ChargeListResponse(
        items=[_charge_to_response(c) for c in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/charges/{charge_id}", response_model=ChargeDetailResponse, summary="收费单详情（含处方收据快照）")
def charge_detail(charge_id: int, db: Session = Depends(get_db)):
    charge = db.query(Charge).filter(Charge.id == charge_id).first()
    if not charge:
        raise HTTPException(status_code=404, detail="收费单不存在")
    data = ChargeDetailResponse.model_validate(charge)
    prescription = (
        db.query(Prescription)
        .options(joinedload(Prescription.items), joinedload(Prescription.acupoints), joinedload(Prescription.injections))
        .filter(Prescription.id == charge.prescription_id)
        .first()
    )
    if prescription:
        data.prescription = PrescriptionResponse.model_validate(prescription).model_dump()
    return data


@router.post("/charges/{charge_id}/pay", response_model=ChargeResponse, summary="收款（待收费 -> 已收费）")
def pay_charge(
    charge_id: int,
    payload: PayRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    charge = db.query(Charge).filter(Charge.id == charge_id).first()
    if not charge:
        raise HTTPException(status_code=404, detail="收费单不存在")
    if charge.status != "待收费":
        raise HTTPException(status_code=400, detail=f"该收费单状态为「{charge.status}」，不可收款")
    apply_payment(charge, payload.payment_method, payload.paid, current_user)
    _transition(db, charge.id, "待收费", "已收费")
    db.commit()
    db.refresh(charge)
    return _charge_to_response(charge)


@router.post("/charges/{charge_id}/refund", response_model=ChargeResponse, summary="退费（已收费 -> 已退费）")
def refund_charge(
    charge_id: int,
    payload: RefundRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    charge = db.query(Charge).filter(Charge.id == charge_id).first()
    if not charge:
        raise HTTPException(status_code=404, detail="收费单不存在")
    # 实退金额落库，支持部分退费；原因必填由 schema + 服务层双重保证
    refund_charge_record(charge, payload.refund_amount, payload.reason, current_user)
    _transition(db, charge.id, "已收费", "已退费")
    db.commit()
    db.refresh(charge)
    return _charge_to_response(charge)


@router.post("/charges/{charge_id}/cancel", response_model=ChargeResponse, summary="作废（待收费 -> 已取消）")
def cancel_charge(
    charge_id: int,
    payload: CancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """开错单（金额错、挂号费录错）可作废，避免「待收费」列表被无效单污染。"""
    charge = db.query(Charge).filter(Charge.id == charge_id).first()
    if not charge:
        raise HTTPException(status_code=404, detail="收费单不存在")
    cancel_charge_record(charge, payload.reason, current_user)
    _transition(db, charge.id, "待收费", "已取消")
    db.commit()
    db.refresh(charge)
    return _charge_to_response(charge)


@router.get("/charges/stats/summary", summary="收费汇总（按日期范围）")
def charge_stats(
    start_date: str | None = Query(None, description="起 yyyy-mm-dd"),
    end_date: str | None = Query(None, description="止 yyyy-mm-dd"),
    db: Session = Depends(get_db),
):
    """返回日期范围内各状态金额汇总，用于收费台概览 / 日结。

    口径统一：收款与退款都基于「实收」(paid / refund_amount)，不再用 payable 冒充退款额；
    每个累加项都经 _to_decimal 量化，避免 Decimal 与 float 混算产生分位漂移。
      collected_amount 累计实收(gross) - refunded_amount 实退 = net_amount 净营收
      paid_amount     当前「已收费」单的净收（向后兼容旧字段）
      overpaid_amount 多收未找零合计，供收银员解释实收与应付的差额
    """
    q = db.query(Charge)
    if start_date:
        q = q.filter(Charge.created_at >= start_date)
    if end_date:
        q = q.filter(Charge.created_at < end_date + " 23:59:59")
    charges = q.all()
    paid_amount = Decimal("0.00")
    refunded_amount = Decimal("0.00")
    collected_amount = Decimal("0.00")
    pending_amount = Decimal("0.00")
    overpaid_amount = Decimal("0.00")
    paid_count = refunded_count = pending_count = cancelled_count = 0
    for c in charges:
        paid = _to_decimal(c.paid)
        refunded = _to_decimal(c.refund_amount)
        if c.status == "已收费":
            paid_amount += _to_decimal(paid - refunded)
            paid_count += 1
        elif c.status == "已退费":
            refunded_amount += _to_decimal(refunded)
            refunded_count += 1
        elif c.status == "待收费":
            pending_amount += _to_decimal(c.payable)
            pending_count += 1
        elif c.status == "已取消":
            cancelled_count += 1
        if c.status in ("已收费", "已退费"):
            collected_amount += _to_decimal(paid)
            overpaid_amount += _to_decimal(c.overpaid)
    net_amount = _to_decimal(collected_amount - refunded_amount)
    return {
        "paid_amount": float(_to_decimal(paid_amount)),
        "refunded_amount": float(_to_decimal(refunded_amount)),
        "pending_amount": float(_to_decimal(pending_amount)),
        "collected_amount": float(_to_decimal(collected_amount)),
        "net_amount": float(net_amount),
        "overpaid_amount": float(_to_decimal(overpaid_amount)),
        "paid_count": paid_count,
        "refunded_count": refunded_count,
        "pending_count": pending_count,
        "cancelled_count": cancelled_count,
        "total_count": len(charges),
    }
