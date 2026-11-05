"""就诊记录 ORM 模型"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, JSON, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Visit(Base):
    """就诊记录 — 中医特色: 含四诊信息 + 辨证论治"""
    __tablename__ = "visits"
    __table_args__ = (
        Index("idx_visits_patient_date", "patient_id", "visit_date"),
        Index("idx_visits_registered_at", "registered_at"),
        Index("idx_visits_status", "status"),
        # 并发兜底：同日排队号唯一。非挂号就诊 queue_no 为 NULL，SQLite 允许多个 NULL，互不影响。
        UniqueConstraint("visit_date", "queue_no", name="uq_visits_date_queue"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    visit_date: Mapped[str] = mapped_column(String(20), nullable=False, comment="就诊日期")
    # 就诊类型：初诊 / 复诊（同一病种的首次为初诊，其后为复诊）
    visit_type: Mapped[str | None] = mapped_column(String(10), comment="就诊类型: 初诊/复诊", default="初诊")

    # 主诉与病史
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False, comment="主诉")
    present_illness: Mapped[str | None] = mapped_column(Text, comment="现病史")

    # 四诊信息 (核心中医特色字段)
    observation: Mapped[str | None] = mapped_column(Text, comment="望诊: 面色、神态、形体")
    auscultation: Mapped[str | None] = mapped_column(Text, comment="闻诊: 语声、呼吸、气味")
    inquiry: Mapped[str | None] = mapped_column(Text, comment="问诊: 寒热汗出饮食睡眠二便等")
    palpation: Mapped[str | None] = mapped_column(Text, comment="切诊: 脉象描述")
    tongue_body: Mapped[str | None] = mapped_column(String(50), comment="舌质: 如'舌红'")
    tongue_coat: Mapped[str | None] = mapped_column(String(50), comment="舌苔: 如'苔黄腻'")
    pulse: Mapped[str | None] = mapped_column(String(100), comment="脉象: 如'弦滑数'")

    # 中医诊断 (理法方药)
    tcm_disease: Mapped[str | None] = mapped_column(String(100), comment="中医病名: 如'胃脘痛'")
    tcm_syndrome: Mapped[str | None] = mapped_column(String(100), comment="证型: 如'肝气犯胃证'")
    treatment_method: Mapped[str | None] = mapped_column(String(100), comment="治法: 如'疏肝理气'")
    ai_analysis: Mapped[str | None] = mapped_column(Text, comment="AI 辅助辨证完整分析(含依据，供病历参考)", default=None)

    # 受控词条关联 (引用 dictionary_terms, 可选; 为空时仍可用上方原文)
    tongue_body_term_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("dictionary_terms.id", ondelete="SET NULL"), comment="舌质词条ID")
    tongue_coat_term_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("dictionary_terms.id", ondelete="SET NULL"), comment="舌苔词条ID")
    pulse_term_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("dictionary_terms.id", ondelete="SET NULL"), comment="脉象词条ID(主脉象，向后兼容)")
    pulse_term_ids: Mapped[list | None] = mapped_column(JSON, comment="脉象词条ID列表(支持多选脉象)")
    syndrome_term_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("dictionary_terms.id", ondelete="SET NULL"), comment="证型词条ID")

    # 影像资料（base64 data URL，作为正式病历资料；亦可经 AI 辨证，但此处独立留存以便查询）
    tongue_image: Mapped[str | None] = mapped_column(Text, comment="舌苔照片 base64 data URL")
    face_image: Mapped[str | None] = mapped_column(Text, comment="面色照片 base64 data URL")
    lab_report_images: Mapped[list | None] = mapped_column(JSON, comment="化验单/影像报告图片列表(base64)")

    # 医嘱
    doctor_notes: Mapped[str | None] = mapped_column(Text, comment="医嘱/调护")
    doctor_id: Mapped[int | None] = mapped_column(Integer, comment="接诊医师ID")
    # 父子关联：复诊指向其初诊，构成一次完整就诊（初诊→复诊链）
    parent_visit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("visits.id", ondelete="SET NULL"), comment="父就诊ID(复诊指向其初诊，构成一次完整就诊)", nullable=True
    )

    # ── 挂号（前台分诊登记）字段：使「挂号 → 就诊 → 开方 → 收费」形成闭环 ──
    queue_no: Mapped[int | None] = mapped_column(Integer, comment="挂号序号(当日排队号)", nullable=True)
    registration_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), comment="挂号费(元)；经收费单按 visit_id 关联收取", nullable=True
    )
    registered_at: Mapped[datetime | None] = mapped_column(DateTime, comment="挂号时间", nullable=True)
    registrar_id: Mapped[int | None] = mapped_column(Integer, comment="挂号员ID", nullable=True)
    department: Mapped[str | None] = mapped_column(String(50), comment="科室/接诊医师(挂号时填写)", nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="待诊", server_default="待诊", comment="就诊状态: 待诊/已接诊/已完成/已取消"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # 乐观锁
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", comment="乐观锁版本号")

    # 关系
    patient: Mapped["Patient"] = relationship(back_populates="visits")
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="visit", cascade="all, delete-orphan")
    tongue_body_term: Mapped["DictionaryTerm | None"] = relationship("DictionaryTerm", foreign_keys=[tongue_body_term_id])
    tongue_coat_term: Mapped["DictionaryTerm | None"] = relationship("DictionaryTerm", foreign_keys=[tongue_coat_term_id])
    pulse_term: Mapped["DictionaryTerm | None"] = relationship("DictionaryTerm", foreign_keys=[pulse_term_id])
    syndrome_term: Mapped["DictionaryTerm | None"] = relationship("DictionaryTerm", foreign_keys=[syndrome_term_id])

    __mapper_args__ = {"version_id_col": version}

    @property
    def tongue_body_term_name(self):
        return self.tongue_body_term.name if self.tongue_body_term else None

    @property
    def tongue_coat_term_name(self):
        return self.tongue_coat_term.name if self.tongue_coat_term else None

    @property
    def pulse_term_name(self):
        return self.pulse_term.name if self.pulse_term else None

    @property
    def syndrome_term_name(self):
        return self.syndrome_term.name if self.syndrome_term else None

    def __repr__(self):
        return f"<Visit(id={self.id}, patient_id={self.patient_id}, date='{self.visit_date}')>"