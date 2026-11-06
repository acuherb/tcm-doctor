"""排班 ORM 模型 — 固定排班表（医生 × 日期 × 时段）"""
from datetime import datetime, date
from sqlalchemy import String, Date, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Schedule(Base):
    """出诊排班：某医生在某天某时段是否出诊。

    设计：每行 = (doctor_id, schedule_date, period) 唯一；period ∈ morning/afternoon/full。
    医生可在同一天同时排上午与下午（两条记录），或排全天（full 一条）。
    删除某行即代表该时段休诊。"""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), comment="出诊医师账号ID"
    )
    schedule_date: Mapped[date] = mapped_column(Date, comment="排班日期")
    period: Mapped[str] = mapped_column(
        String(10), comment="时段: morning(上午) / afternoon(下午) / full(全天)"
    )
    department: Mapped[str | None] = mapped_column(
        String(50), comment="科室快照（冗余存储，便于直接读取，避免每次联表）"
    )
    note: Mapped[str | None] = mapped_column(String(200), comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    __table_args__ = (
        UniqueConstraint(
            "doctor_id", "schedule_date", "period", name="uq_schedule_doc_date_period"
        ),
    )
