"""收费单服务：处方收费与挂号费等非处方收费共用，避免重复逻辑。

create_charge 同时被 billing 路由（处方收费）与 registration 路由（挂号费）调用，
统一处理：金额量化、减免校验、重复开单复用、开单即收、退款与作废。

事务边界：`commit` 由调用方决定。挂号登记需要「患者 + 就诊 + 收费单」同生共死，
故以 commit=False 调用，由路由末尾统一提交；收费台直接开单则沿用默认 commit=True。
"""
import secrets
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.billing import Charge, _to_decimal
from app.models.prescription import Prescription
from app.models.patient import Patient
from app.models.user import User
from app.schemas.billing import ChargeCreate

VALID_METHODS = ("现金", "微信", "支付宝", "银行卡", "医保", "记账")


def generate_charge_no(db: Session) -> str:
    """C + 秒级时间 + 8 位随机十六进制：单秒内约 43 亿种组合，冲突概率可忽略。

    不再依赖「查重后插入」（查到插入之间无锁）；唯一索引是最终兜底，
    由 create_charge 捕获 IntegrityError 后重取单号重试一次。
    db 参数保留以兼容既有调用方。
    """
    return "C" + datetime.now().strftime("%Y%m%d%H%M%S") + secrets.token_hex(4).upper()


def _append_note(note: str | None, text: str) -> str:
    parts = [p for p in (note or "").split("；") if p]
    parts.append(text)
    return "；".join(parts)


def apply_payment(charge: Charge, method: str, paid, current_user: Optional[User]) -> None:
    """落库一次收款：校验方式、统一量化、记录「多收未找零」差额。

    paid 是实际收到的钱（gross），超出 payable 的部分单独记入 overpaid 并附注，
    日结时收银员可解释这笔钱，而不是让它混进营业额。
    """
    if method not in VALID_METHODS:
        raise HTTPException(status_code=400, detail="无效的收款方式")
    paid = _to_decimal(paid)
    payable = _to_decimal(charge.payable)
    if paid < payable:
        raise HTTPException(status_code=400, detail="实收金额小于应付金额")
    overpaid = (paid - payable).max(Decimal("0.00"))
    charge.paid = paid
    charge.overpaid = _to_decimal(overpaid)
    charge.payment_method = method
    charge.status = "已收费"
    if current_user:
        charge.cashier_id = current_user.id
        charge.cashier_name = current_user.display_name or current_user.username
    charge.paid_at = datetime.now()
    if overpaid > 0:
        charge.note = _append_note(charge.note, f"多收未找零 ¥{overpaid:.2f}")


def refund_charge_record(
    charge: Charge, amount, reason: str, current_user: Optional[User],
) -> None:
    """退费（支持部分退费）：实退金额落库，口径一律基于实收 paid。

    paid 本身不改写（保留审计轨迹），净收由 net_paid = paid - refund_amount 表达。
    仅允许从「已收费」退一次；部分退费时单据仍标记「已退费」，差额即诊所留存。
    """
    if charge.status != "已收费":
        raise HTTPException(status_code=400, detail="仅「已收费」的收费单可退费")
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="退费原因必填")
    paid = _to_decimal(charge.paid)
    already = _to_decimal(charge.refund_amount)
    available = (paid - already).max(Decimal("0.00"))
    refund = _to_decimal(amount) if amount is not None else available
    if refund <= 0:
        raise HTTPException(status_code=400, detail="退款金额必须大于 0")
    if refund > available:
        raise HTTPException(status_code=400, detail="退款金额不能超过实收金额")
    charge.refund_amount = _to_decimal(already + refund)
    charge.status = "已退费"
    charge.refunded_by = (current_user.display_name or current_user.username) if current_user else "系统"
    charge.refunded_at = datetime.now()
    charge.refund_reason = reason.strip()
    if refund < paid:
        charge.note = _append_note(charge.note, f"部分退费 ¥{refund:.2f}（实收 ¥{paid:.2f}）")


def cancel_charge_record(
    charge: Charge, reason: str, current_user: Optional[User],
) -> None:
    """作废「待收费」单（开错金额/录错挂号费等），避免待收费列表被污染。"""
    if charge.status != "待收费":
        raise HTTPException(status_code=400, detail="仅「待收费」的收费单可作废")
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="作废原因必填")
    charge.status = "已取消"
    charge.cancelled_by = (current_user.display_name or current_user.username) if current_user else "系统"
    charge.cancelled_at = datetime.now()
    charge.cancel_reason = reason.strip()


def create_charge(
    db: Session, payload: ChargeCreate, current_user: Optional[User] = None,
    commit: bool = True, _retry: int = 0,
) -> Charge:
    """创建收费单。

    - 处方收费（prescription_id 给定）：金额从处方 total_price 快照，且同一处方「待收费」单复用。
    - 非处方收费（挂号费等）：需 amount + (patient_id 或 visit_id)；同 visit_id + kind 的
      「待收费」单复用（接口重试不重复开单）。
    - 传入 payment_method + paid 则直接置「已收费」。
    - commit=False 时只 flush，不提交，供调用方把收费单纳入自己的事务。
    """
    prescription = None
    kind = payload.kind or "prescription"
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
    elif payload.visit_id is not None:
        # 非处方收费幂等：同一就诊、同一类型只保留一张待收费单
        existing = (
            db.query(Charge)
            .filter(
                Charge.prescription_id.is_(None),
                Charge.visit_id == payload.visit_id,
                Charge.kind == kind,
                Charge.status == "待收费",
            )
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

    charge = Charge(
        charge_no=generate_charge_no(db),
        prescription_id=payload.prescription_id,
        patient_id=patient_id,
        visit_id=visit_id,
        patient_name=pname,
        prescription_title=title,
        kind=kind,
        amount=amount,
        discount=discount,
        payable=_to_decimal(amount - discount),
        paid=Decimal("0.00"),
        overpaid=Decimal("0.00"),
        refund_amount=Decimal("0.00"),
        status="待收费",
        note=payload.note,
    )

    # 开单即收
    if payload.payment_method and payload.paid is not None:
        apply_payment(charge, payload.payment_method, payload.paid, current_user)

    # 单号唯一约束兜底：并发撞号时重试一次（重取单号）。
    # 不使用 SAVEPOINT —— pysqlite 默认驱动下 begin_nested() 会连带提交外层事务，
    # 破坏「挂号三件套同生共死」的原子性。commit=False 时把冲突上抛给调用方
    # （register 的整体回滚重试），由调用方决定事务边界。
    try:
        db.add(charge)
        db.flush()
        if commit:
            db.commit()
            db.refresh(charge)
        return charge
    except IntegrityError:
        if not commit:
            raise
        db.rollback()
        if _retry >= 1:
            raise HTTPException(status_code=409, detail="收费单号冲突，请重试")
        return create_charge(db, payload, current_user, commit=True, _retry=1)
