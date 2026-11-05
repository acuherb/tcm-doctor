"""收费管理路由：开方后生成收费单、收款、退费、收据与统计。

与库存/发药解耦：本域只管「钱」的闭环；库存扣减仍在「发药」环节完成。
权限由网关中间件按 /billing 域放行（billing:read / billing:write），此处仅取当前收银员信息。
"""
import logging
import random
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.billing import Charge, _to_decimal
from app.models.prescription import Prescription
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.billing import (
    ChargeCreate, ChargeResponse, ChargeDetailResponse, ChargeListResponse,
    PayRequest, RefundRequest,
)
from app.schemas.prescription import PrescriptionResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["收费管理"])

VALID_METHODS = ("现金", "微信", "支付宝", "银行卡", "医保", "记账")


def _gen_charge_no(db: Session) -> str:
    while True:
        no = "C" + datetime.now().strftime("%Y%m%d%H%M%S") + f"{random.randint(0, 99):02d}"
        if not db.query(Charge).filter(Charge.charge_no == no).first():
            return no


def _charge_to_response(c: Charge) -> ChargeResponse:
    return ChargeResponse.model_validate(c)


@router.post("/charges", response_model=ChargeResponse, summary="开具收费单（可同时收款）")
def create_charge(
    payload: ChargeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """为处方生成收费单（prescription_id 给定）；或创建非处方收费（如挂号费，prescription_id 留空）。

    传入收款方式与实收金额则直接置为「已收费」。同一处方已有「待收费」单时复用，避免重复开单。
    """
    from app.services.billing_service import create_charge as _svc_create

    charge = _svc_create(db, payload, current_user)
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
    if charge.status == "已收费":
        raise HTTPException(status_code=400, detail="该收费单已收款")
    if charge.status == "已退费":
        raise HTTPException(status_code=400, detail="该收费单已退费，无法收款")
    if payload.payment_method not in VALID_METHODS:
        raise HTTPException(status_code=400, detail="无效的收款方式")
    paid = _to_decimal(payload.paid)
    if paid < charge.payable:
        raise HTTPException(status_code=400, detail="实收金额小于应付金额")

    charge.paid = paid
    charge.payment_method = payload.payment_method
    charge.status = "已收费"
    charge.cashier_id = current_user.id
    charge.cashier_name = current_user.display_name or current_user.username
    charge.paid_at = datetime.now()
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
    if charge.status != "已收费":
        raise HTTPException(status_code=400, detail="仅「已收费」的收费单可退费")
    charge.status = "已退费"
    charge.refunded_by = current_user.display_name or current_user.username
    charge.refunded_at = datetime.now()
    charge.refund_reason = payload.reason
    db.commit()
    db.refresh(charge)
    return _charge_to_response(charge)


@router.get("/charges/stats/summary", summary="收费汇总（按日期范围）")
def charge_stats(
    start_date: str | None = Query(None, description="起 yyyy-mm-dd"),
    end_date: str | None = Query(None, description="止 yyyy-mm-dd"),
    db: Session = Depends(get_db),
):
    """返回日期范围内各状态金额汇总，用于收费台概览。"""
    q = db.query(Charge)
    if start_date:
        q = q.filter(Charge.created_at >= start_date)
    if end_date:
        q = q.filter(Charge.created_at < end_date + " 23:59:59")
    charges = q.all()
    paid_amount = Decimal("0.00")
    refunded_amount = Decimal("0.00")
    pending_amount = Decimal("0.00")
    paid_count = refunded_count = pending_count = 0
    for c in charges:
        if c.status == "已收费":
            paid_amount += c.paid
            paid_count += 1
        elif c.status == "已退费":
            refunded_amount += c.payable
            refunded_count += 1
        else:
            pending_amount += c.payable
            pending_count += 1
    return {
        "paid_amount": float(paid_amount),
        "refunded_amount": float(refunded_amount),
        "pending_amount": float(pending_amount),
        "paid_count": paid_count,
        "refunded_count": refunded_count,
        "pending_count": pending_count,
        "total_count": len(charges),
    }
