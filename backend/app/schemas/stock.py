"""库存统一 Pydantic 模型（物品/批次/流水/总览/预警/盘点）"""
from datetime import datetime
from pydantic import BaseModel, Field


# === 物品主数据 ===

class StockItemBase(BaseModel):
    item_type: str = Field("其他", description="类别: 中药/针灸针/艾灸耗材/外治耗材/其他")
    name: str = Field(..., min_length=1, max_length=100, description="名称")
    spec: str | None = Field(None, description="规格")
    unit: str = Field("g", description="计量单位 g/盒/支/根/贴/包")
    sell_price: float | None = Field(None, description="默认售价(按单位)")
    herb_id: int | None = Field(None, description="关联药材(仅中药)")
    min_stock: float | None = Field(None, description="物品级最低库存预警(按单位)")
    is_active: bool = Field(True, description="是否启用")


class StockItemCreate(StockItemBase):
    pass


class StockItemUpdate(BaseModel):
    item_type: str | None = None
    name: str | None = None
    spec: str | None = None
    unit: str | None = None
    sell_price: float | None = None
    herb_id: int | None = None
    min_stock: float | None = None
    is_active: bool | None = None


class StockItemResponse(StockItemBase):
    id: int
    total_quantity: float = 0.0  # 实时总量(正常/近效期批次合计)

    model_config = {"from_attributes": True}


# === 批次 ===

class StockBatchBase(BaseModel):
    item_id: int
    batch_number: str | None = None
    quantity: float = Field(..., gt=0, description="数量(按物品单位)")
    unit_price: float | None = None
    sale_price: float | None = None
    purchase_date: str | None = None
    expiry_date: str | None = None
    supplier: str | None = None
    min_stock: float | None = None
    location: str | None = None
    status: str | None = "正常"


class StockBatchIn(StockBatchBase):
    note: str | None = Field(None, description="入库备注")


class StockBatchOut(StockBatchBase):
    item_id: int | None = None  # 出库时可选指定批次，否则 FIFO
    batch_id: int | None = None  # 指定扣减批次；为空则按批次顺序 FIFO
    note: str | None = None


class StockBatchResponse(StockBatchBase):
    id: int
    item_name: str | None = None
    unit: str = "g"
    herb_id: int | None = None  # 关联药材(仅中药物品)；前端按药材筛批次时使用

    model_config = {"from_attributes": True}


class StockBatchUpdate(BaseModel):
    quantity: float | None = None
    unit_price: float | None = None
    sale_price: float | None = None
    batch_number: str | None = None
    purchase_date: str | None = None
    expiry_date: str | None = None
    supplier: str | None = None
    min_stock: float | None = None
    location: str | None = None
    status: str | None = None


# === 流水 ===

class StockTransactionResponse(BaseModel):
    id: int
    item_id: int
    item_name: str | None = None
    unit: str | None = None
    batch_id: int | None = None
    batch_number: str | None = None
    transaction_type: str
    quantity: float
    before_quantity: float | None = None
    after_quantity: float | None = None
    reference_id: int | None = None
    reference_type: str | None = None
    operator: str | None = None
    note: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# === 总览 / 预警 ===

class StockOverview(BaseModel):
    item_id: int
    item_name: str
    item_type: str
    unit: str
    total_quantity: float
    batch_count: int
    min_stock: float | None
    has_alert: bool


class StockAlert(BaseModel):
    item_id: int
    item_name: str
    unit: str
    current_quantity: float
    min_stock: float
    alert_type: str  # 低于最低库存/近效期


# === 盘点 ===

class StockCheckAdjustment(BaseModel):
    batch_id: int
    counted: float = Field(..., ge=0, description="实盘数量")


class StockCheckIn(BaseModel):
    item_id: int
    note: str | None = None
    adjustments: list[StockCheckAdjustment] = Field(..., min_length=1, description="逐批次实盘调整")
