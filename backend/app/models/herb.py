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
    category: Mapped[str | None] = mapped_column(String(30), comment="分类: 解表药/清热药/...")
    nature: Mapped[str | None] = mapped_column(String(20), comment="药性: 寒/热/温/凉/平")
    flavor: Mapped[str | None] = mapped_column(String(50), comment="药味: 甘/苦/辛/...")
    meridian_tropism: Mapped[str | None] = mapped_column(String(100), comment="归经(旧: 自由文本, 已并入 meridians)")
    # —— 多维标签化（按《神农本草经》三品 + 四气五味归经升降浮沉）——
    grade: Mapped[str | None] = mapped_column(String(10), comment="三品: 上品/中品/下品")
    flavors: Mapped[list | None] = mapped_column(JSON, comment="五味标签(多值): 辛/甘/酸/苦/咸/淡/涩")
    meridians: Mapped[list | None] = mapped_column(JSON, comment="归经标签(多值): 十二经等")
    directions: Mapped[list | None] = mapped_column(JSON, comment="升降浮沉(多值): 升/降/浮/沉")
    tags: Mapped[list | None] = mapped_column(JSON, comment="通用标签: 功效分类/主治证型/经方常用/产地/炮制")
    efficacy: Mapped[str | None] = mapped_column(Text, comment="功效/主治")
    contraindication: Mapped[str | None] = mapped_column(Text, comment="禁忌")
    dosage_min: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="最小剂量(g)")
    dosage_max: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="最大剂量(g)")
    toxicity: Mapped[str] = mapped_column(String(10), default="无毒", comment="毒性")
    pregnancy_contraindicated: Mapped[bool] = mapped_column(Boolean, default=False, comment="孕妇禁忌")
    storage_condition: Mapped[str | None] = mapped_column(String(100), comment="储存条件")
    price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="参考单价(元/g)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    # 关系
    inventory_items: Mapped[list["HerbInventory"]] = relationship(back_populates="herb", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Herb(id={self.id}, name='{self.name}')>"





class HerbInventory(Base):
    """中药饮片库存"""
    __tablename__ = "herb_inventory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    herb_id: Mapped[int] = mapped_column(Integer, ForeignKey("herbs.id"), nullable=False)
    batch_number: Mapped[str | None] = mapped_column(String(50), comment="批号")
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, comment="库存量(g)")
    unit_price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="进价(元/g)")
    sale_price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="售价(元/g)")
    purchase_date: Mapped[str | None] = mapped_column(String(10), comment="购入日期")
    expiry_date: Mapped[str | None] = mapped_column(String(10), comment="有效期")
    supplier: Mapped[str | None] = mapped_column(String(100), comment="供应商")
    min_stock: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="最低库存预警")
    location: Mapped[str | None] = mapped_column(String(50), comment="存放位置")
    status: Mapped[str] = mapped_column(String(20), default="正常", comment="状态")

    herb: Mapped["Herb"] = relationship(back_populates="inventory_items")

    def __repr__(self):
        return f"<HerbInventory(herb_id={self.herb_id}, qty={self.quantity})>"


class InventoryTransaction(Base):
    """库存出入库记录"""
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    herb_id: Mapped[int] = mapped_column(Integer, ForeignKey("herbs.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="入库/出库/损耗")
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    before_quantity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    after_quantity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    reference_id: Mapped[int | None] = mapped_column(Integer, comment="关联处方ID")
    note: Mapped[str | None] = mapped_column(Text, comment="备注")
    operator: Mapped[str | None] = mapped_column(String(50), comment="操作人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<InventoryTransaction(herb_id={self.herb_id}, type='{self.transaction_type}', qty={self.quantity})>"