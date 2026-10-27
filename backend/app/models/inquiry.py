"""问诊十问记录 ORM 模型 — 保存每次问诊十问的原始答案与评估结果，形成病例信息链"""
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InquiryRecord(Base):
    """经方家问诊十问记录"""
    __tablename__ = "inquiry_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False, comment="患者ID")
    visit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visits.id"), comment="关联就诊ID(可为空，向后兼容旧记录)")
    primary_type: Mapped[str | None] = mapped_column(String(50), comment="主偏性画像，如 少阴·里寒")
    answers: Mapped[dict | None] = mapped_column(JSON, comment="原始答案: {问诊key: 选项key}")
    notes: Mapped[dict | None] = mapped_column(JSON, comment="自填备注: {问诊key: 补充描述}")
    result: Mapped[dict | None] = mapped_column(JSON, comment="评估结果(六经分布/判据解析/方域提示)")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="评估时间")