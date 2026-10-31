"""药品相关 Pydantic 模型"""
from datetime import datetime
from pydantic import BaseModel, Field


# === 药材 ===

class HerbCreate(BaseModel):
    """创建药材"""
    name: str = Field(..., min_length=1, max_length=50, description="正名")
    aliases: list[str] | None = Field(None, description="异名列表")
    nature: str | None = Field(None, description="四气")
    flavors: list[str] | None = Field(None, description="五味标签(多值): 辛/甘/酸/苦/咸/淡/涩")
    efficacy: str | None = Field(None, description="主治")
    contraindication: str | None = Field(None, description="禁忌")
    dosage_min: float | None = Field(None, description="最小剂量(g)")
    dosage_max: float | None = Field(None, description="最大剂量(g)")
    toxicity: str = Field("无毒", description="毒性")
    pregnancy_contraindicated: bool = Field(False, description="孕妇禁忌")
    storage_condition: str | None = Field(None, description="储存条件")
    price: float | None = Field(None, description="参考单价(元/g)")
    is_active: bool = Field(True, description="是否启用（停用则在字典中隐藏）")


class HerbUpdate(BaseModel):
    """更新药材"""
    name: str | None = None
    aliases: list[str] | None = None
    nature: str | None = None
    flavors: list[str] | None = None
    efficacy: str | None = None
    contraindication: str | None = None
    dosage_min: float | None = None
    dosage_max: float | None = None
    toxicity: str | None = None
    pregnancy_contraindicated: bool | None = None
    storage_condition: str | None = None
    price: float | None = None
    is_active: bool | None = None


class HerbResponse(BaseModel):
    """药材响应"""
    id: int
    name: str
    aliases: list[str] | None
    nature: str | None
    flavors: list[str] | None
    efficacy: str | None
    contraindication: str | None
    dosage_min: float | None
    dosage_max: float | None
    toxicity: str | None
    pregnancy_contraindicated: bool | None
    storage_condition: str | None
    price: float | None = None
    is_active: bool | None

    model_config = {"from_attributes": True}


# === 库存 ===

class InventoryIn(BaseModel):
    """入库"""
    herb_id: int
    quantity: float = Field(..., gt=0, description="入库量(g)")
    unit_price: float | None = Field(None, description="进价(元/g)")
    sale_price: float | None = Field(None, description="售价(元/g)")
    batch_number: str | None = None
    purchase_date: str | None = None
    expiry_date: str | None = None
    supplier: str | None = None
    note: str | None = None


class InventoryOut(BaseModel):
    """出库"""
    herb_id: int
    quantity: float = Field(..., gt=0, description="出库量(g)")
    reference_id: int | None = Field(None, description="关联处方ID")
    note: str | None = None


class InventoryResponse(BaseModel):
    """库存响应"""
    id: int
    herb_id: int
    herb_name: str | None = None
    batch_number: str | None
    quantity: float
    unit_price: float | None
    sale_price: float | None
    purchase_date: str | None
    expiry_date: str | None
    supplier: str | None
    min_stock: float | None
    location: str | None
    status: str | None

    model_config = {"from_attributes": True}


class InventoryAlert(BaseModel):
    """库存预警"""
    herb_id: int
    herb_name: str
    current_quantity: float
    min_stock: float
    alert_type: str  # 低于最低库存/近效期


class InventoryUpdate(BaseModel):
    """更新库存记录(预警/仓位等)"""
    min_stock: float | None = None
    location: str | None = None
    status: str | None = None


class InventorySummary(BaseModel):
    """库存汇总(按药材)"""
    herb_id: int
    herb_name: str
    total_quantity: float
    batch_count: int
    min_stock: float | None
    has_alert: bool