"""针灸相关 Pydantic 模型"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AcupointCreate(BaseModel):
    """新增/编辑腧穴"""
    name: str
    meridian: str | None = None
    location: str | None = None
    efficacy: str | None = None
    point_type: str | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AcupointUpdate(BaseModel):
    name: str | None = None
    meridian: str | None = None
    location: str | None = None
    efficacy: str | None = None
    point_type: str | None = None
    notes: str | None = None


class AcupointResponse(BaseModel):
    id: int
    name: str
    meridian: str | None
    location: str | None
    efficacy: str | None
    point_type: str | None
    notes: str | None
    is_active: bool
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AcupointFormulaCreate(BaseModel):
    """新增/编辑针灸方"""
    name: str
    aliases: list[str] | None = None
    source: str | None = None
    efficacy: str | None = None
    indications: str | None = None
    usage: str | None = None
    technique: str | None = None
    treatment_frequency: str | None = None
    treatment_days: int | None = None
    composition: dict = {"acupoints": []}
    notes: str | None = None


class AcupointFormulaUpdate(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    source: str | None = None
    efficacy: str | None = None
    indications: str | None = None
    usage: str | None = None
    technique: str | None = None
    treatment_frequency: str | None = None
    treatment_days: int | None = None
    composition: dict | None = None
    notes: str | None = None


class AcupointFormulaResponse(BaseModel):
    id: int
    name: str
    aliases: list[str] | None
    source: str | None
    efficacy: str | None
    indications: str | None
    usage: str | None
    technique: str | None
    treatment_frequency: str | None
    treatment_days: int | None
    composition: dict
    notes: str | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)