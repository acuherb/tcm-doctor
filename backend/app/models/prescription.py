"""处方 ORM 模型"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, Integer, Numeric, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ClassicFormula(Base):
    """经典方剂库"""
    __tablename__ = "classic_formulas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="方名")
    aliases: Mapped[dict | None] = mapped_column(JSON, comment="别名")
    source: Mapped[str | None] = mapped_column(String(100), comment="出处: 伤寒论/金匮要略/...")
    composition: Mapped[dict] = mapped_column(JSON, nullable=False, comment="组成")
    efficacy: Mapped[str | None] = mapped_column(Text, comment="功效")
    indications: Mapped[str | None] = mapped_column(Text, comment="主治")
    usage: Mapped[str | None] = mapped_column(Text, comment="用法")
    modifications: Mapped[dict | None] = mapped_column(JSON, comment="加减变化")

    def __repr__(self):
        return f"<ClassicFormula(id={self.id}, name='{self.name}')>"


class Prescription(Base):
    """处方记录"""
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(Integer, ForeignKey("visits.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False)
    formula_name: Mapped[str | None] = mapped_column(String(100), comment="方名")
    is_classic: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否经典方")
    classic_formula_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("classic_formulas.id"))
    acupoint_formula_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("acupoint_formulas.id"), comment="关联针灸方库")
    preparation_method: Mapped[str] = mapped_column(String(50), default="水煎服", comment="煎法")
    administration: Mapped[str | None] = mapped_column(String(100), comment="服法")
    doses: Mapped[int] = mapped_column(Integer, default=7, comment="剂数")
    doctor_notes: Mapped[str | None] = mapped_column(Text, comment="医嘱")
    total_price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="总价")
    prescription_type: Mapped[str] = mapped_column(String(20), default="药方", comment="处方类型: 药方/针方/针剂/混合")
    # 针灸方顶层字段（可与药方共存于同一张处方）
    acupoint_formula_name: Mapped[str | None] = mapped_column(String(100), comment="针灸方案名")
    acupoint_technique: Mapped[str | None] = mapped_column(String(50), comment="针灸针法/治法")
    treatment_frequency: Mapped[str | None] = mapped_column(String(20), comment="操作频次: 每日/隔日/每周...")
    treatment_days: Mapped[int | None] = mapped_column(Integer, comment="疗程天数")
    acupuncture_fee: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="针灸费用(元)")
    status: Mapped[str] = mapped_column(String(20), default="已开", comment="状态")
    reviewed_by: Mapped[int | None] = mapped_column(Integer, comment="审核人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # 关系
    visit: Mapped["Visit"] = relationship(back_populates="prescriptions")
    items: Mapped[list["PrescriptionItem"]] = relationship(back_populates="prescription", cascade="all, delete-orphan")
    acupoints: Mapped[list["AcupointPrescription"]] = relationship(back_populates="prescription", cascade="all, delete-orphan")
    injections: Mapped[list["PrescriptionInjection"]] = relationship(back_populates="prescription", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Prescription(id={self.id}, formula='{self.formula_name}', status='{self.status}')>"


class PrescriptionItem(Base):
    """处方药味明细"""
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prescription_id: Mapped[int] = mapped_column(Integer, ForeignKey("prescriptions.id"), nullable=False)
    herb_id: Mapped[int] = mapped_column(Integer, ForeignKey("herbs.id"), nullable=False)
    herb_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="药材名(冗余)")
    dose: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, comment="剂量(g)")
    special_method: Mapped[str | None] = mapped_column(String(20), comment="特殊煎法")
    is_king_herb: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否君药")
    note: Mapped[str | None] = mapped_column(String(100), comment="备注")

    prescription: Mapped["Prescription"] = relationship(back_populates="items")

    def __repr__(self):
        return f"<PrescriptionItem(herb='{self.herb_name}', dose={self.dose}g)>"


class AcupointPrescription(Base):
    """处方针灸配穴细目"""
    __tablename__ = "acupoint_prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prescription_id: Mapped[int] = mapped_column(Integer, ForeignKey("prescriptions.id"), nullable=False)
    acupoint_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("acupoints.id"), comment="穴位ID(允许手输，可为空)")
    acupoint_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="穴名(冗余)")
    technique: Mapped[str | None] = mapped_column(String(50), comment="针法：毫针泻法/补法/温灸...")
    retention: Mapped[str | None] = mapped_column(String(20), comment="留针时间")
    sequence: Mapped[int] = mapped_column(Integer, default=1, comment="施针顺序")
    note: Mapped[str | None] = mapped_column(String(100), comment="备注")

    prescription: Mapped["Prescription"] = relationship(back_populates="acupoints")

    def __repr__(self):
        return f"<AcupointPrescription(acupoint='{self.acupoint_name}', technique='{self.technique}')>"


class PrescriptionInjection(Base):
    """处方针剂细目"""
    __tablename__ = "prescription_injections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prescription_id: Mapped[int] = mapped_column(Integer, ForeignKey("prescriptions.id"), nullable=False)
    drug_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="药品名称")
    spec: Mapped[str | None] = mapped_column(String(50), comment="规格")
    dose: Mapped[str | None] = mapped_column(String(50), comment="用量")
    usage: Mapped[str | None] = mapped_column(String(50), comment="用法: 肌注/静滴/皮试...")
    frequency: Mapped[str | None] = mapped_column(String(30), comment="频次")
    note: Mapped[str | None] = mapped_column(String(100), comment="备注")

    prescription: Mapped["Prescription"] = relationship(back_populates="injections")

    def __repr__(self):
        return f"<PrescriptionInjection(drug='{self.drug_name}', dose='{self.dose}')>"