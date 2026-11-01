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
    min_stock: float | None = None
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
    min_stock: float | None = None
    is_active: bool | None

    model_config = {"from_attributes": True}


