"""收费单相关 Pydantic 模型

金额统一以 float（元）在接口层表达；入库时由路由层量化为 Decimal(12,2)，避免浮点累积误差。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class ChargeCreate(BaseModel):
    # 处方收费（默认）：传 prescription_id，金额从处方快照自动计算
    prescription_id: Optional[int] = Field(default=None, description="关联处方(处方收费时必填)")
    # 非处方收费（如挂号费）：传 amount + (patient_id 或 visit_id)，prescription_id 留空
    visit_id: Optional[int] = Field(default=None, description="关联就诊(挂号费等非处方收费)")
    patient_id: Optional[int] = Field(default=None, description="关联患者")
    amount: Optional[float] = Field(default=None, ge=0, description="应收原价(非处方收费时填)")
    kind: str = Field(default="prescription", description="收费类型: prescription/registration")
    title: Optional[str] = Field(default=None, description="标题快照(非处方收费，如'挂号费')")
    patient_name: Optional[str] = Field(default=None, description="患者姓名快照(非处方收费时填)")
    discount: float = Field(default=0.0, ge=0, description="减免金额（元）")
    # 开单同时收款：传入收款方式与实收金额则直接置为「已收费」
    payment_method: Optional[str] = Field(default=None, description="收款方式: 现金/微信/支付宝/银行卡/医保/记账")
    paid: Optional[float] = Field(default=None, ge=0, description="实收金额（元），开单即收时填写")
    note: Optional[str] = Field(default=None, description="备注")


class PayRequest(BaseModel):
    payment_method: str = Field(..., description="收款方式")
    paid: float = Field(..., ge=0, description="实收金额（元）")


class RefundRequest(BaseModel):
    # 财务审计：退费必须留原因
    reason: str = Field(..., min_length=1, max_length=200, description="退费原因（必填）")
    # 部分退费：留空表示全额退（退 = 实收 paid）
    refund_amount: Optional[float] = Field(default=None, gt=0, description="实际退款金额，留空=全额退款")


class CancelRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200, description="作废原因（必填）")


class ChargeResponse(BaseModel):
    id: int
    charge_no: str
    prescription_id: Optional[int] = None
    patient_id: Optional[int] = None
    visit_id: Optional[int] = None
    patient_name: Optional[str] = None
    prescription_title: Optional[str] = None
    kind: str = "prescription"
    amount: float = 0.0
    discount: float = 0.0
    payable: float = 0.0
    paid: float = 0.0
    overpaid: float = 0.0
    refund_amount: float = 0.0
    payment_method: Optional[str] = None
    status: str
    cashier_name: Optional[str] = None
    paid_at: Optional[datetime] = None
    refunded_by: Optional[str] = None
    refunded_at: Optional[datetime] = None
    refund_reason: Optional[str] = None
    cancelled_by: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def net_paid(self) -> float:
        """净收 = 实收 - 实退；已退费单据据此不会把退掉的钱当成营业额。"""
        v = Decimal(str(self.paid or 0)) - Decimal(str(self.refund_amount or 0))
        return float(v.quantize(Decimal("0.01")))


class ChargeDetailResponse(ChargeResponse):
    # 收据所需：关联的处方明细（药味/配穴/针剂）快照，便于打印
    prescription: Optional[dict] = None


class ChargeListResponse(BaseModel):
    items: list[ChargeResponse]
    total: int
    page: int
    page_size: int
