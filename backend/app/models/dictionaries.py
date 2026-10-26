"""主数据字典 ORM 模型 —— 受控词表"""
from datetime import datetime
from sqlalchemy import String, Text, Boolean, Integer, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DictionaryTerm(Base):
    """受控词条: term_type 区分 syndrome(证型)/tongue(舌象)/pulse(脉象)"""
    __tablename__ = "dictionary_terms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    term_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    aliases: Mapped[list | None] = mapped_column(JSON, comment="同义词")
    description: Mapped[str | None] = mapped_column(Text, comment="释义")
    meridian: Mapped[str | None] = mapped_column(String(30), comment="六经归属(仅证型)")
    category: Mapped[str | None] = mapped_column(String(50), comment="证型分类")
    aspect: Mapped[str | None] = mapped_column(String(10), comment="舌质/舌苔(仅舌象)")
    attributes: Mapped[list | None] = mapped_column(JSON, comment="附属特征(仅舌象)")
    pulse_type: Mapped[str | None] = mapped_column(String(30), comment="脉类(仅脉象)")
    clinical_meaning: Mapped[str | None] = mapped_column(Text, comment="临床主病(仅脉象)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<DictionaryTerm(type='{self.term_type}', name='{self.name}')>"