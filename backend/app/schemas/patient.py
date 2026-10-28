"""患者相关 Pydantic 模型"""
from datetime import datetime
from pydantic import BaseModel, Field


# === 患者 ===

class PatientCreate(BaseModel):
    """创建患者"""
    name: str = Field(..., min_length=1, max_length=50, description="姓名")
    gender: str | None = Field(None, description="性别")
    birth_date: str | None = Field(None, description="出生日期")
    phone: str | None = Field(None, description="电话")
    id_card: str | None = Field(None, description="身份证号")
    address: str | None = Field(None, description="地址")
    allergy_history: str | None = Field(None, description="过敏史")
    medical_history: str | None = Field(None, description="既往史")
    notes: str | None = Field(None, description="备注")


class PatientUpdate(BaseModel):
    """更新患者"""
    name: str | None = Field(None, min_length=1, max_length=50)
    gender: str | None = None
    birth_date: str | None = None
    phone: str | None = None
    id_card: str | None = None
    address: str | None = None
    allergy_history: str | None = None
    medical_history: str | None = None
    constitution_type: str | None = None
    constitution_score: dict | None = None
    notes: str | None = None


class PatientResponse(BaseModel):
    """患者响应"""
    id: int
    name: str
    gender: str | None
    birth_date: str | None
    phone: str | None
    id_card: str | None
    address: str | None
    allergy_history: str | None
    medical_history: str | None
    constitution_type: str | None
    constitution_score: dict | None
    notes: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class PatientListResponse(BaseModel):
    """患者列表响应(分页)"""
    total: int
    items: list[PatientResponse]
    page: int
    page_size: int


# === 就诊记录 ===

class VisitCreate(BaseModel):
    """创建就诊记录"""
    visit_date: str = Field(..., description="就诊日期")
    chief_complaint: str = Field(..., min_length=1, description="主诉")
    present_illness: str | None = Field(None, description="现病史")
    # 四诊信息
    observation: str | None = Field(None, description="望诊")
    auscultation: str | None = Field(None, description="闻诊")
    inquiry: str | None = Field(None, description="问诊")
    palpation: str | None = Field(None, description="切诊")
    tongue_body: str | None = Field(None, description="舌质")
    tongue_coat: str | None = Field(None, description="舌苔")
    pulse: str | None = Field(None, description="脉象")
    # 中医诊断
    tcm_disease: str | None = Field(None, description="中医病名")
    tcm_syndrome: str | None = Field(None, description="证型")
    treatment_method: str | None = Field(None, description="治法")
    ai_analysis: str | None = Field(None, description="AI 辅助辨证完整分析(含依据)")
    # 受控词条关联(可选; 指向 /api/v1/dictionaries 的 id)
    tongue_body_term_id: int | None = Field(None, description="舌质词条ID")
    tongue_coat_term_id: int | None = Field(None, description="舌苔词条ID")
    pulse_term_id: int | None = Field(None, description="脉象词条ID")
    syndrome_term_id: int | None = Field(None, description="证型词条ID")
    # 医嘱
    doctor_notes: str | None = Field(None, description="医嘱")
    doctor_id: int | None = Field(None, description="接诊医师ID")


class VisitUpdate(BaseModel):
    """更新就诊记录（全字段可选，仅更新传入字段）"""
    visit_date: str | None = Field(None, description="就诊日期")
    chief_complaint: str | None = Field(None, description="主诉")
    present_illness: str | None = Field(None, description="现病史")
    observation: str | None = Field(None, description="望诊")
    auscultation: str | None = Field(None, description="闻诊")
    inquiry: str | None = Field(None, description="问诊")
    palpation: str | None = Field(None, description="切诊")
    tongue_body: str | None = Field(None, description="舌质")
    tongue_coat: str | None = Field(None, description="舌苔")
    pulse: str | None = Field(None, description="脉象")
    tcm_disease: str | None = Field(None, description="中医病名")
    tcm_syndrome: str | None = Field(None, description="证型")
    treatment_method: str | None = Field(None, description="治法")
    ai_analysis: str | None = Field(None, description="AI 辅助辨证完整分析(含依据)")
    tongue_body_term_id: int | None = Field(None, description="舌质词条ID")
    tongue_coat_term_id: int | None = Field(None, description="舌苔词条ID")
    pulse_term_id: int | None = Field(None, description="脉象词条ID")
    syndrome_term_id: int | None = Field(None, description="证型词条ID")
    doctor_notes: str | None = Field(None, description="医嘱")
    doctor_id: int | None = Field(None, description="接诊医师ID")


class VisitResponse(BaseModel):
    """就诊记录响应"""
    id: int
    patient_id: int
    visit_date: str
    chief_complaint: str
    present_illness: str | None
    observation: str | None
    auscultation: str | None
    inquiry: str | None
    palpation: str | None
    tongue_body: str | None
    tongue_coat: str | None
    pulse: str | None
    tcm_disease: str | None
    tcm_syndrome: str | None
    treatment_method: str | None
    ai_analysis: str | None
    tongue_body_term_id: int | None
    tongue_coat_term_id: int | None
    pulse_term_id: int | None
    syndrome_term_id: int | None
    tongue_body_term_name: str | None
    tongue_coat_term_name: str | None
    pulse_term_name: str | None
    syndrome_term_name: str | None
    doctor_notes: str | None
    doctor_id: int | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


# === 体质辨识 ===

class ConstitutionSubmit(BaseModel):
    """提交经方家问诊十问"""
    answers: dict[str, str] = Field(..., description="问诊答案: {问诊key: 选项key}")
    notes: dict[str, str] = Field(default_factory=dict, description="自填描述: {问诊key: 补充文字}")
    visit_id: int | None = Field(None, description="关联就诊ID(可为空，向后兼容旧记录)")


class InquiryRecordOut(BaseModel):
    """问诊十问记录"""
    id: int
    patient_id: int
    visit_id: int | None = None
    primary_type: str | None
    answers: dict | None
    notes: dict | None
    result: dict | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ConstitutionResult(BaseModel):
    """体质辨识(倪师问诊十问)结果"""
    primary_type: str = Field(..., description="主偏性画像，如 少阴·肾阳亏虚 / 少阴+太阴 合病")
    primary_meridians: list[str] = Field(default_factory=list, description="主证六经(按主次排序，合病时多于一项)")
    scores: dict[str, int] = Field(..., description="六经各命中点数")
    secondary_types: list[str] = Field(default_factory=list, description="倾向六经")
    findings: list[str] = Field(default_factory=list, description="命中的症状判据")
    suggestion: str = Field(..., description="倪师思路(接方域提示)")
    detail: dict = Field(default_factory=dict, description="偏性明细")