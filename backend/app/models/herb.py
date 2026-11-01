"""药材 ORM 模型"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, Integer, Numeric, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Herb(Base):
    """中药材字典"""
    __tablename__ = "herbs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="正名")
    aliases: Mapped[dict | None] = mapped_column(JSON, comment="异名列表")
    nature: Mapped[str | None] = mapped_column(String(20), comment="四气: 寒/热/温/凉/平")
    flavors: Mapped[list | None] = mapped_column(JSON, comment="五味标签(多值): 辛/甘/酸/苦/咸/淡/涩")
    efficacy: Mapped[str | None] = mapped_column(Text, comment="主治")
    contraindication: Mapped[str | None] = mapped_column(Text, comment="禁忌")
    dosage_min: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="最小剂量(g)")
    dosage_max: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="最大剂量(g)")
    toxicity: Mapped[str] = mapped_column(String(10), default="无毒", comment="毒性")
    pregnancy_contraindicated: Mapped[bool] = mapped_column(Boolean, default=False, comment="孕妇禁忌")
    storage_condition: Mapped[str | None] = mapped_column(String(100), comment="储存条件")
    price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="参考单价(元/g)")
    min_stock: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="最低库存预警(药材级, g)")
    grade: Mapped[str | None] = mapped_column(String(20), comment="等级/规格")
    meridians: Mapped[list | None] = mapped_column(JSON, comment="归经(十二经数组)")
    directions: Mapped[list | None] = mapped_column(JSON, comment="升降浮沉")
    tags: Mapped[list | None] = mapped_column(JSON, comment="标签数组")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    def __repr__(self):
        return f"<Herb(id={self.id}, name='{self.name}')>"





