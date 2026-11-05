"""收费单创建服务：处方收费与挂号费等非处方收费共用，避免重复逻辑。

create_charge 同时被 billing 路由（处方收费）与 registration 路由（挂号费）调用，
统一处理：金额量化、减免校验、重复开单复用、开单即收。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.billing import Charge, _to_decimal
from app.models.prescription import Prescription
from app.models.patient import Patient
from app.models.user import User
from app.schemas.billing import ChargeCreate

VALID_METHODS = ("现金", "微信", "支付宝", "银行卡", "医保", "记账")


def generate_charge_no(db: Session) -> str:
    import random

    while True:
        no = "C" + datetime.now().strftime("%Y%m%d%H%M%S") + f"{random.randint(0, 99):02d}"
        if not db.query(Charge).filter(Charge.charge_no == no).first():
            return no


def create_charge(db: Session, payload: ChargeCreate, current_user: Optional[User] = None) -> Charge:
    """创建收费单。

    - 处方收费（prescription_id 给定）：金额从处方 total_price 快照，且同一处方「待收费」单复用。
    - 非处方收费（挂号费等）：需 amount + (patient_id 或 visit_id)，用 payload 中的快照信息。
    - 传入 payment_method + paid 则直接置「已收费」。
    """
    prescription = None
    if payload.prescription_id:
        prescription = db.query(Prescription).filter(Prescription.id == payload.prescription_id).first()
        if not prescription:
            raise HTTPException(status_code=404, detail="处方不存在")
        if prescription.status == "已取消":
            raise HTTPException(status_code=400, detail="已取消的处方不可收费")
        existing = (
            db.query(Charge)
            .filter(Charge.prescription_id == prescription.id, Charge.status == "待收费")
            .first()
        )
        if existing:
            return existing

    if prescription:
        amount = _to_decimal(prescription.total_price or 0)
        patient_id = prescription.patient_id
        visit_id = prescription.visit_id
        title = prescription.formula_name or "自拟方"
        pname = None
        if patient_id:
            pat = db.query(Patient).filter(Patient.id == patient_id).first()
            pname = pat.name if pat else None
    else:
        if payload.amount is None or (payload.patient_id is None and payload.visit_id is None):
            raise HTTPException(status_code=400, detail="非处方收费需提供 amount 及 patient_id/visit_id")
        amount = _to_decimal(payload.amount)
        patient_id = payload.patient_id
        visit_id = payload.visit_id
        title = payload.title
        pname = payload.patient_name

    discount = _to_decimal(payload.discount)
    if discount > amount:
        raise HTTPException(status_code=400, detail="减免金额不能超过应收原价")
    payable = (amount - discount).max(Decimal("0.00"))

    charge = Charge(
        charge_no=generate_charge_no(db),
        prescription_id=payload.prescription_id,
        patient_id=patient_id,
        visit_id=visit_id,
        patient_name=pname,
        prescription_title=title,
        kind=payload.kind or "prescription",
        amount=amount,
        discount=discount,
        payable=payable,
        paid=Decimal("0.00"),
        status="待收费",
        note=payload.note,
    )

    # 开单即收
    if payload.payment_method and payload.paid is not None:
        if payload.payment_method not in VALID_METHODS:
            raise HTTPException(status_code=400, detail="无效的收款方式")
        paid = _to_decimal(payload.paid)
        if paid < payable:
            raise HTTPException(status_code=400, detail="实收金额小于应付金额")
        charge.paid = paid
        charge.payment_method = payload.payment_method
        charge.status = "已收费"
        if current_user:
            charge.cashier_id = current_user.id
            charge.cashier_name = current_user.display_name or current_user.username
        charge.paid_at = datetime.now()

    db.add(charge)
    db.commit()
    db.refresh(charge)
    return charge
