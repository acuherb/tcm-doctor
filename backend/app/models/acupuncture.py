"""针灸 ORM 模型"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Acupoint(Base):
    """腧穴字典"""
    __tablename__ = "acupoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="穴名")
    meridian: Mapped[str | None] = mapped_column(String(50), comment="归经: 手阳明大肠经 等")
    location: Mapped[str | None] = mapped_column(String(200), comment="定位")
    efficacy: Mapped[str | None] = mapped_column(Text, comment="功效")
    point_type: Mapped[str | None] = mapped_column(String(20), comment="类型: 井穴/荥穴/输穴/原穴...")
    notes: Mapped[str | None] = mapped_column(Text, comment="备注")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Acupoint(name='{self.name}', meridian='{self.meridian}')>"


class AcupointFormula(Base):
    """针灸方库 — 把一组穴位按方名固化成可复用针灸方"""
    __tablename__ = "acupoint_formulas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="针灸方名")
    aliases: Mapped[dict | None] = mapped_column(JSON, comment="别名")
    source: Mapped[str | None] = mapped_column(String(100), comment="出处: 倪海厦·针灸 / 通用 ...")
    efficacy: Mapped[str | None] = mapped_column(Text, comment="功效")
    indications: Mapped[str | None] = mapped_column(Text, comment="主治")
    usage: Mapped[str | None] = mapped_column(Text, comment="操作要点/注意事项")
    # 默认针灸属性（引入处方时回填 Prescription 的 4 个新字段）
    technique: Mapped[str | None] = mapped_column(String(50), comment="默认针法/治法")
    treatment_frequency: Mapped[str | None] = mapped_column(String(20), comment="默认操作频次: 每日/隔日/每周...")
    treatment_days: Mapped[int | None] = mapped_column(Integer, comment="默认疗程天数")
    composition: Mapped[dict] = mapped_column(JSON, nullable=False, comment="组成: {acupoints:[...]}")
    notes: Mapped[str | None] = mapped_column(Text, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<AcupointFormula(id={self.id}, name='{self.name}')>"