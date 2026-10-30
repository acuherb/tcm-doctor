"""随访提醒 ORM 模型 —— 处方用药后自动/手动生成的复诊回访提醒"""
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FollowUpReminder(Base):
    """随访提醒: 疗程结束/指定日期后提醒医师回访该患者"""
    __tablename__ = "followup_reminders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False, index=True, comment="患者ID")
    due_date: Mapped[str] = mapped_column(String(20), nullable=False, comment="应回访日期 YYYY-MM-DD")
    source_type: Mapped[str] = mapped_column(String(20), default="prescription", comment="来源: prescription(处方自动)/manual(手动)")
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="来源处方ID")
    status: Mapped[str] = mapped_column(String(20), default="pending", comment="pending/done/cancelled")
    note: Mapped[str | None] = mapped_column(Text, comment="备注/复诊建议")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<FollowUpReminder(id={self.id}, patient_id={self.patient_id}, due='{self.due_date}', status='{self.status}')>"
