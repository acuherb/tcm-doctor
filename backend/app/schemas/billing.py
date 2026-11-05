"""收费单相关 Pydantic 模型

金额统一以 float（元）在接口层表达；入库时由路由层量化为 Decimal(12,2)，避免浮点累积误差。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChargeCreate(BaseModel):
    prescription_id: int
    discount: float = Field(default=0.0, ge=0, description="减免金额（元）")
    # 开单同时收款：传入收款方式与实收金额则直接置为「已收费」
    payment_method: Optional[str] = Field(default=None, description="收款方式: 现金/微信/支付宝/银行卡/医保/记账")
    paid: Optional[float] = Field(default=None, ge=0, description="实收金额（元），开单即收时填写")
    note: Optional[str] = Field(default=None, description="备注")


class PayRequest(BaseModel):
    payment_method: str = Field(..., description="收款方式")
    paid: float = Field(..., ge=0, description="实收金额（元）")


class RefundRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="退费原因")


class ChargeResponse(BaseModel):
    id: int
    charge_no: str
    prescription_id: int
    patient_id: Optional[int] = None
    visit_id: Optional[int] = None
    patient_name: Optional[str] = None
    prescription_title: Optional[str] = None
    amount: float = 0.0
    discount: float = 0.0
    payable: float = 0.0
    paid: float = 0.0
    payment_method: Optional[str] = None
    status: str
    cashier_name: Optional[str] = None
    paid_at: Optional[datetime] = None
    refunded_by: Optional[str] = None
    refunded_at: Optional[datetime] = None
    refund_reason: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChargeDetailResponse(ChargeResponse):
    # 收据所需：关联的处方明细（药味/配穴/针剂）快照，便于打印
    prescription: Optional[dict] = None


class ChargeListResponse(BaseModel):
    items: list[ChargeResponse]
    total: int
    page: int
    page_size: int
