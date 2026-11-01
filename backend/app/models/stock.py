"""库存统一模型：物品-批次-流水 三件套（替代 herb_inventory / inventory_transactions）

设计：库存本质是关于"物品"的管理，中药只是物品的一种(item_type='中药'，可选关联 herbs 字典)。
耗材(针灸针/艾灸/外治)以相同结构管理，单位由 stock_items.unit 决定(g/盒/支/根/贴/包)，不再写死。
"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StockItem(Base):
    """库存物品主数据（中药/针灸针/艾灸耗材/外治耗材/其他）"""
    __tablename__ = "stock_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_type: Mapped[str] = mapped_column(String(20), default="其他", comment="类别: 中药/针灸针/艾灸耗材/外治耗材/其他")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="名称")
    spec: Mapped[str | None] = mapped_column(String(100), comment="规格")
    unit: Mapped[str] = mapped_column(String(10), default="g", comment="计量单位 g/盒/支/根/贴/包")
    sell_price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="默认售价(按单位)")
    herb_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("herbs.id"), comment="关联药材(仅中药)")
    min_stock: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="物品级最低库存预警(按单位)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    batches: Mapped[list["StockBatch"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    transactions: Mapped[list["StockTransaction"]] = relationship(back_populates="item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StockItem(id={self.id}, name='{self.name}', type='{self.item_type}')>"


class StockBatch(Base):
    """库存批次（替代 herb_inventory）"""
    __tablename__ = "stock_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("stock_items.id"), nullable=False)
    batch_number: Mapped[str | None] = mapped_column(String(50), comment="批号")
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0, comment="数量(按物品单位)")
    unit_price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="进价(按单位)")
    sale_price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="售价(按单位)")
    purchase_date: Mapped[str | None] = mapped_column(String(10), comment="购入日期 YYYY-MM-DD")
    expiry_date: Mapped[str | None] = mapped_column(String(10), comment="有效期 YYYY-MM-DD")
    supplier: Mapped[str | None] = mapped_column(String(100), comment="供应商")
    min_stock: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="批次级最低库存(遗留,主用物品级)")
    location: Mapped[str | None] = mapped_column(String(50), comment="存放位置")
    status: Mapped[str] = mapped_column(String(20), default="正常", comment="状态 正常/近效期/呆滞/损耗")

    item: Mapped["StockItem"] = relationship(back_populates="batches")

    def __repr__(self):
        return f"<StockBatch(item_id={self.item_id}, qty={self.quantity})>"


class StockTransaction(Base):
    """库存流水（替代 inventory_transactions）：入了多少/出了多少/剩余多少全靠它追溯"""
    __tablename__ = "stock_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("stock_items.id"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stock_batches.id"), comment="关联批次(可为空)")
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="入库/出库/损耗/盘点/调整")
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, comment="变动数量(可正可负)")
    before_quantity: Mapped[float | None] = mapped_column(Numeric(12, 3), comment="变动前(物品总量)")
    after_quantity: Mapped[float | None] = mapped_column(Numeric(12, 3), comment="变动后(物品总量)")
    reference_id: Mapped[int | None] = mapped_column(Integer, comment="关联业务ID(处方/盘点单)")
    reference_type: Mapped[str | None] = mapped_column(String(20), comment="处方/就诊/盘点/手动")
    operator: Mapped[str | None] = mapped_column(String(50), comment="操作人")
    note: Mapped[str | None] = mapped_column(Text, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    item: Mapped["StockItem"] = relationship(back_populates="transactions")

    def __repr__(self):
        return f"<StockTransaction(item_id={self.item_id}, type='{self.transaction_type}', qty={self.quantity})>"
