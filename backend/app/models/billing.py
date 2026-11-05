"""收费单（处方 -> 收费 / 挂号费 等非处方收费）ORM 模型。

业务定位：开方后生成收费单，记录应收/实收/收款方式与收银员，可打印收据；
与发药/库存解耦（库存仍由「发药」环节扣减），此处只管「钱」的闭环。
kind 区分收费类型：prescription=处方收费，registration=挂号费（无处方）。
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Integer, String, Numeric, DateTime, Text, Index, ForeignKey, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(Decimal("0.01"))


class Charge(Base):
    __tablename__ = "charges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 收费单号：C + 时间(精确到秒) + 2 位随机数，保证可读且唯一
    charge_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, comment="收费单号")

    prescription_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("prescriptions.id", ondelete="SET NULL"), nullable=True, index=True,
        comment="关联处方（挂号费等非处方收费可为空）",
    )
    patient_id: Mapped[int | None] = mapped_column(Integer, index=True, comment="关联患者")
    visit_id: Mapped[int | None] = mapped_column(Integer, comment="关联就诊")
    # 冗余快照，便于收据/统计直接展示，不随患者改名而变
    patient_name: Mapped[str | None] = mapped_column(String(50), comment="患者姓名(快照)")
    prescription_title: Mapped[str | None] = mapped_column(String(120), comment="处方标题(快照)")
    # 收费类型：prescription=处方收费；registration=挂号费（无处方）
    kind: Mapped[str] = mapped_column(
        String(20), default="prescription", server_default="prescription",
        comment="收费类型: prescription/registration",
    )

    # 金额（元）：amount 为处方原始总价快照，payable = amount - discount
    # paid 为「实际收到的钱」(gross，退费后不改写，保留审计轨迹)；net_paid = paid - refund_amount
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), comment="应收原价")
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), comment="减免")
    payable: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), comment="应付")
    paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), comment="实收(gross，退费后不变)")
    # 多收未找零：paid - payable 的正差额，单独落库，避免日结时无法解释这笔钱
    overpaid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), comment="多收未找零金额")
    # 实退金额：支持部分退费；退款统计一律以此为准（不再用 payable 冒充）
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), comment="实际退费金额")

    payment_method: Mapped[str | None] = mapped_column(String(20), comment="收款方式: 现金/微信/支付宝/银行卡/医保/记账")
    status: Mapped[str] = mapped_column(String(20), default="待收费", comment="状态: 待收费/已收费/已退费/已取消")

    cashier_id: Mapped[int | None] = mapped_column(Integer, comment="收银员ID")
    cashier_name: Mapped[str | None] = mapped_column(String(50), comment="收银员姓名")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, comment="收款时间")

    refunded_by: Mapped[str | None] = mapped_column(String(50), comment="退费人")
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, comment="退费时间")
    refund_reason: Mapped[str | None] = mapped_column(String(200), comment="退费原因")

    # 作废审计（仅「待收费」可作废）
    cancelled_by: Mapped[str | None] = mapped_column(String(50), comment="作废人")
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, comment="作废时间")
    cancel_reason: Mapped[str | None] = mapped_column(String(200), comment="作废原因")

    note: Mapped[str | None] = mapped_column(Text, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_charges_status", "status"),
        Index("idx_charges_created_at", "created_at"),
        Index("idx_charges_patient_created", "patient_id", "created_at"),
        # 一处方只能有一笔「在账」的钱：待收费/已收费 互斥。
        # 已退费、已取消是终态历史，不占用唯一性（退费后可合法重新开单）。
        # 挂号费等非处方收费按 (visit_id, kind) 同理，允许多个 NULL（处方收费 visit_id 也可能重复）。
        Index(
            "uq_charges_prescription_active", "prescription_id",
            unique=True,
            sqlite_where=text("kind = 'prescription' AND status IN ('待收费', '已收费')"),
        ),
    )

    def __repr__(self):
        return f"<Charge(id={self.id}, no='{self.charge_no}', status='{self.status}')>"
