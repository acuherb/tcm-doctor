"""处方相关 Pydantic 模型"""
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class PrescriptionItemCreate(BaseModel):
    """处方药味"""
    herb_id: int
    herb_name: str
    dose: float = Field(..., gt=0, description="剂量(g)")
    special_method: str | None = Field(None, description="特殊煎法")
    is_king_herb: bool = False
    note: str | None = None


class AcupointPrescriptionCreate(BaseModel):
    """处方针灸配穴"""
    acupoint_id: int | None = Field(None, description="穴位ID(可从库中选择)")
    acupoint_name: str = Field(..., description="穴名")
    technique: str | None = Field(None, description="针法：毫针泻法/补法/温灸...")
    retention: str | None = Field(None, description="留针时间")
    sequence: int = Field(1, ge=1, description="施针顺序")
    note: str | None = None


class PrescriptionInjectionCreate(BaseModel):
    """处方针剂细目"""
    drug_name: str = Field(..., description="药品名称")
    spec: str | None = Field(None, description="规格")
    dose: str | None = Field(None, description="用量")
    usage: str | None = Field(None, description="用法: 肌注/静滴/皮试...")
    frequency: str | None = Field(None, description="频次")
    note: str | None = None


class PrescriptionCreate(BaseModel):
    """创建处方"""
    visit_id: int
    patient_id: int
    formula_name: str | None = Field(None, description="方名")
    is_classic: bool = False
    classic_formula_id: int | None = None
    acupoint_formula_id: int | None = None
    preparation_method: str = "水煎服"
    administration: str | None = None
    doses: int = Field(7, ge=1, description="剂数")
    doctor_notes: str | None = None
    prescription_type: str = Field("药方", description="处方类型: 药方/针方/针剂/混合")
    # 针灸方顶层字段（可与药方共存于同一张处方）
    acupoint_formula_name: str | None = Field(None, description="针灸方案名")
    acupoint_technique: str | None = Field(None, description="针灸针法/治法")
    treatment_frequency: str | None = Field(None, description="操作频次: 每日/隔日/每周...")
    treatment_days: int | None = Field(None, description="疗程天数")
    follow_up_date: str | None = Field(None, description="建议复诊日期 YYYY-MM-DD（可选，用于自动生成随访提醒）")
    acupuncture_fee: float | None = Field(None, description="针灸费用(元)")
    items: list[PrescriptionItemCreate] = Field(default_factory=list, description="药味列表")
    acupoints: list[AcupointPrescriptionCreate] = Field(default_factory=list, description="针灸配穴列表")
    injections: list[PrescriptionInjectionCreate] = Field(default_factory=list, description="针剂列表")

    @model_validator(mode="after")
    def _at_least_one_side(self):
        if not self.items and not self.acupoints and not self.injections:
            raise ValueError("请至少填写一味药、一个配穴或一支针剂")
        return self


class PrescriptionItemResponse(BaseModel):
    """处方药味响应"""
    id: int
    herb_id: int
    herb_name: str
    dose: float
    special_method: str | None
    is_king_herb: bool
    note: str | None

    model_config = {"from_attributes": True}


class AcupointPrescriptionResponse(BaseModel):
    """处方针灸配穴响应"""
    id: int
    acupoint_id: int | None
    acupoint_name: str
    technique: str | None
    retention: str | None
    sequence: int
    note: str | None

    model_config = {"from_attributes": True}


class PrescriptionInjectionResponse(BaseModel):
    """处方针剂细目响应"""
    id: int
    drug_name: str
    spec: str | None
    dose: str | None
    usage: str | None
    frequency: str | None
    note: str | None

    model_config = {"from_attributes": True}


class PrescriptionResponse(BaseModel):
    """处方响应"""
    id: int
    visit_id: int
    patient_id: int
    patient_name: str | None = None
    formula_name: str | None
    is_classic: bool
    classic_formula_id: int | None
    acupoint_formula_id: int | None
    preparation_method: str
    administration: str | None
    doses: int
    doctor_notes: str | None
    total_price: float | None
    prescription_type: str = "药方"
    # 针灸方顶层字段（可与药方共存于同一张处方）
    acupoint_formula_name: str | None = None
    acupoint_technique: str | None = None
    treatment_frequency: str | None = None
    treatment_days: int | None = None
    acupuncture_fee: float | None = None
    status: str
    reviewed_by: int | None
    created_at: datetime | None
    items: list[PrescriptionItemResponse] = []
    acupoints: list[AcupointPrescriptionResponse] = []
    injections: list[PrescriptionInjectionResponse] = []

    model_config = {"from_attributes": True}


class ClassicFormulaCreate(BaseModel):
    """新增/编辑经典方剂"""
    name: str
    aliases: list[str] | None = None
    source: str | None = None
    composition: dict | None = None
    efficacy: str | None = None
    indications: str | None = None
    usage: str | None = None
    modifications: dict | None = None


class ClassicFormulaResponse(BaseModel):
    """经典方剂响应"""
    id: int
    name: str
    aliases: list[str] | None
    source: str | None
    composition: dict | list | None
    efficacy: str | None
    indications: str | None
    usage: str | None
    modifications: dict | list | None

    model_config = {"from_attributes": True}