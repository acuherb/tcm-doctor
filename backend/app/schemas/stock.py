"""库存统一 Pydantic 模型（物品/批次/流水/总览/预警/供应商/采购/报表）"""
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
    barcode: str | None = Field(None, description="条码")
    default_supplier_id: int | None = Field(None, description="默认供应商")


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
    barcode: str | None = None
    default_supplier_id: int | None = None


class StockItemResponse(StockItemBase):
    id: int
    total_quantity: float = 0.0  # 实时总量(正常/近效期批次合计)
    stock_value: float = 0.0     # 库存金额(进价×数量合计)

    model_config = {"from_attributes": True}


# === 批次 ===

class StockBatchBase(BaseModel):
    item_id: int
    batch_number: str | None = None
    quantity: float = Field(..., ge=0, description="数量(按物品单位，可为0表示扣空)")
    unit_price: float | None = Field(None, description="进价(单位成本)")
    purchase_date: str | None = None
    expiry_date: str | None = None
    supplier: str | None = None
    supplier_id: int | None = Field(None, description="供应商ID")
    min_stock: float | None = None
    location: str | None = None
    status: str | None = "正常"
    barcode: str | None = None


class StockBatchIn(StockBatchBase):
    quantity: float = Field(..., gt=0, description="入库数量(须为正)")
    note: str | None = Field(None, description="入库备注")


class StockBatchOut(StockBatchBase):
    item_id: int | None = None  # 出库时可选指定批次，否则 FIFO
    quantity: float = Field(..., gt=0, description="出库数量(须为正)")
    batch_id: int | None = None  # 指定扣减批次；为空则按批次顺序 FIFO
    unit_price: float | None = Field(None, ge=0, description="出库单价(元/单位)；0 或留空表示赠送/内部领用，仅记录去向不计入收入")
    note: str | None = None


class StockBatchResponse(StockBatchBase):
    id: int
    item_name: str | None = None
    unit: str = "g"
    herb_id: int | None = None  # 关联药材(仅中药物品)；前端按药材筛批次时使用
    sell_price: float | None = None  # 物品默认售价；前端「按批次取价」据此回填单价

    model_config = {"from_attributes": True}


class StockBatchUpdate(BaseModel):
    quantity: float | None = None
    unit_price: float | None = None
    batch_number: str | None = None
    purchase_date: str | None = None
    expiry_date: str | None = None
    supplier: str | None = None
    supplier_id: int | None = None
    min_stock: float | None = None
    location: str | None = None
    status: str | None = None
    barcode: str | None = None


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
    unit_cost: float | None = None
    unit_price: float | None = None
    cost_amount: float | None = None
    revenue_amount: float | None = None
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
    stock_value: float = 0.0  # 库存金额(进价×数量)


class StockAlert(BaseModel):
    item_id: int
    item_name: str
    item_type: str | None = None
    unit: str
    current_quantity: float
    min_stock: float | None = None
    alert_type: str  # 低于最低库存/近效期/呆滞/高价值积压
    expiry_date: str | None = None
    days_to_expiry: int | None = None
    last_move_days: int | None = None
    stock_value: float | None = None


# === 盘点 ===

class StockAdjustIn(BaseModel):
    item_id: int
    counted: float = Field(..., ge=0, description="实盘数量(按物品单位)")
    note: str | None = None


# === 供应商 ===

class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    contact: str | None = None
    phone: str | None = None
    address: str | None = None
    note: str | None = None
    is_active: bool = True


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact: str | None = None
    phone: str | None = None
    address: str | None = None
    note: str | None = None
    is_active: bool | None = None


class SupplierResponse(SupplierBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# === 采购入库 ===

class PurchaseItemIn(BaseModel):
    item_id: int
    batch_number: str | None = None
    quantity: float = Field(..., gt=0, description="采购数量")
    unit_price: float = Field(..., gt=0, description="进价(单位成本)")
    expiry_date: str | None = None
    location: str | None = None


class PurchaseOrderCreate(BaseModel):
    supplier_id: int | None = None
    order_date: str | None = None
    note: str | None = None
    items: list[PurchaseItemIn] = Field(..., min_length=1)


class PurchaseItemResponse(BaseModel):
    id: int
    item_id: int
    item_name: str | None = None
    batch_number: str | None = None
    quantity: float
    unit_price: float
    amount: float
    expiry_date: str | None = None
    location: str | None = None

    model_config = {"from_attributes": True}


class PurchaseOrderResponse(BaseModel):
    id: int
    order_no: str
    supplier_id: int | None = None
    supplier_name: str | None = None
    order_date: str | None = None
    note: str | None = None
    status: str
    total_amount: float
    operator: str | None = None
    created_at: datetime
    items: list[PurchaseItemResponse] = []

    model_config = {"from_attributes": True}


# === 报表 ===

class ReportSummary(BaseModel):
    period_start: str | None = None
    period_end: str | None = None
    purchase_cost: float = 0.0       # 期间采购成本
    sales_revenue: float = 0.0       # 期间销售收入
    cogs: float = 0.0                # 期间销售成本(COGS)
    gross_profit: float = 0.0        # 毛利
    gross_margin: float = 0.0        # 毛利率(0-1)
    ending_inventory_value: float = 0.0  # 期末库存金额


class ReportProfitItem(BaseModel):
    item_id: int
    item_name: str
    unit: str
    revenue: float = 0.0
    cogs: float = 0.0
    gross_profit: float = 0.0
    gross_margin: float = 0.0


class ReportABCItem(BaseModel):
    item_id: int
    item_name: str
    unit: str
    stock_value: float = 0.0
    value_ratio: float = 0.0   # 占库存总额比例
    cumulative_ratio: float = 0.0
    category: str = "C"         # A/B/C


class ReportTurnover(BaseModel):
    item_id: int
    item_name: str
    unit: str
    cogs: float = 0.0
    avg_inventory_value: float = 0.0
    turnover: float = 0.0       # 周转率 = COGS / 平均库存金额


class SupplierPriceRow(BaseModel):
    item_id: int
    item_name: str
    unit: str
    supplier_name: str
    min_cost: float
    max_cost: float
    avg_cost: float
    last_cost: float


# === 库存选项(类别/单位) ===

class StockOptionBase(BaseModel):
    opt_type: str = Field(..., pattern="^(category|unit)$", description="类型: category 物品类别 / unit 计量单位")
    name: str = Field(..., min_length=1, max_length=60, description="选项名称")
    color: str | None = Field(None, description="自定义颜色(HEX)，用于选项标签着色")
    is_active: bool = True


class StockOptionCreate(StockOptionBase):
    pass


class StockOptionUpdate(BaseModel):
    opt_type: str | None = Field(None, pattern="^(category|unit)$")
    name: str | None = Field(None, min_length=1, max_length=60)
    color: str | None = Field(None, description="自定义颜色(HEX)")
    is_active: bool | None = None


class StockOptionResponse(StockOptionBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}