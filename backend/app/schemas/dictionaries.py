"""数据字典层 —— 中医受控词表(证型/舌象/脉象)"""
from datetime import datetime
from pydantic import BaseModel, Field

TERM_TYPES = ("syndrome", "tongue", "pulse", "tag")


class DictTermCreate(BaseModel):
    term_type: str = Field(..., pattern="^(syndrome|tongue|pulse|tag)$", description="词类: syndrome/舌象 tongue/脉象 pulse/tag 患者标签")
    name: str = Field(..., min_length=1, max_length=60, description="词项正名")
    aliases: list[str] | None = Field(None, description="同义词")
    description: str | None = Field(None, description="释义")
    meridian: str | None = Field(None, description="六经归属(仅 syndrome)")
    category: str | None = Field(None, description="证型分类(仅 syndrome)")
    aspect: str | None = Field(None, pattern="^(舌质|舌苔)$", description="舌象维度(仅 tongue)")
    attributes: list[str] | None = Field(None, description="附属特征(仅 tongue)")
    pulse_type: str | None = Field(None, description="脉类(仅 pulse)")
    clinical_meaning: str | None = Field(None, description="临床主病(仅 pulse)")


class DictTermUpdate(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    description: str | None = None
    meridian: str | None = None
    category: str | None = None
    aspect: str | None = None
    attributes: list[str] | None = None
    pulse_type: str | None = None
    clinical_meaning: str | None = None
    is_active: bool | None = None
    term_type: str | None = Field(None, pattern="^(syndrome|tongue|pulse|tag)$")


class DictTermResponse(BaseModel):
    id: int
    term_type: str
    name: str
    aliases: list[str] | None
    description: str | None
    meridian: str | None
    category: str | None
    aspect: str | None
    attributes: list[str] | None
    pulse_type: str | None
    clinical_meaning: str | None
    is_active: bool
    created_at: datetime | None
    model_config = {"from_attributes": True}