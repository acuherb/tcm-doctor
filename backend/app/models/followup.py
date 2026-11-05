"""病情跟踪 ORM 模型 —— 治疗后的效果反馈/随访记录"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FollowUp(Base):
    """病情跟踪: 中药/针灸治疗后的效果反馈，便于复诊时调整方案"""
    __tablename__ = "followups"
    __table_args__ = (
        Index("idx_followups_patient", "patient_id"),
        Index("idx_followups_visit", "visit_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, comment="患者ID")
    visit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visits.id", ondelete="CASCADE"), nullable=True, comment="关联的治疗就诊(可选)")
    followup_date: Mapped[str] = mapped_column(String(20), nullable=False, comment="随访/反馈日期")
    treatment_type: Mapped[str | None] = mapped_column(String(20), comment="治疗类型: 中药/针灸/其他")
    improvement: Mapped[str | None] = mapped_column(String(20), comment="改善程度: 明显好转/好转/稳定/反复/加重")
    feedback: Mapped[str | None] = mapped_column(Text, comment="效果反馈/症状变化描述")
    doctor_id: Mapped[int | None] = mapped_column(Integer, comment="记录医师ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # 乐观锁
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", comment="乐观锁版本号")

    patient: Mapped["Patient"] = relationship(back_populates="followups")

    __mapper_args__ = {"version_id_col": version}

    def __repr__(self):
        return f"<FollowUp(id={self.id}, patient_id={self.patient_id}, date='{self.followup_date}')>"
