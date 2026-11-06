"""库存统一模型：物品-批次-流水 三件套（替代 herb_inventory / inventory_transactions）

设计：库存本质是关于"物品"的管理，中药只是物品的一种(item_type='中药'，可选关联 herbs 字典)。
耗材(针灸针/艾灸/外治)以相同结构管理，单位由 stock_items.unit 决定(g/盒/支/根/贴/包)，不再写死。

进销存财务化：流水(StockTransaction)在数量维度之外，额外记录金额维度
(unit_cost 单位成本 / unit_price 单位售价 / cost_amount 成本金额 / revenue_amount 收入金额)，
使得任意期间的采购成本、销售成本(COGS)、收入、毛利都能直接聚合得出。
"""
from datetime import datetime

from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Numeric, ForeignKey, Date, UniqueConstraint, Index,
)
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
    sell_price: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="默认售价(按单位)")
    herb_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("herbs.id", ondelete="SET NULL"), comment="关联药材(仅中药)")
    min_stock: Mapped[float | None] = mapped_column(Numeric(12, 3), comment="物品级最低库存预警(按单位)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    barcode: Mapped[str | None] = mapped_column(String(40), unique=True, comment="条码(扫码快速录入)")
    default_supplier_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), comment="默认供应商")

    batches: Mapped[list["StockBatch"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    transactions: Mapped[list["StockTransaction"]] = relationship(back_populates="item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StockItem(id={self.id}, name='{self.name}', type='{self.item_type}')>"


class StockBatch(Base):
    """库存批次（替代 herb_inventory）。批次只保留进价(unit_price)，售价以物品级为准。"""
    __tablename__ = "stock_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("stock_items.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_number: Mapped[str | None] = mapped_column(String(50), comment="批号")
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0, comment="数量(按物品单位)")
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="进价(单位成本, 按单位)")
    purchase_date: Mapped[str | None] = mapped_column(String(10), comment="购入日期 YYYY-MM-DD")
    expiry_date: Mapped[str | None] = mapped_column(String(10), comment="有效期 YYYY-MM-DD")
    supplier: Mapped[str | None] = mapped_column(String(100), comment="供应商名称(冗余, 便于历史追溯)")
    supplier_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), comment="供应商ID")
    min_stock: Mapped[float | None] = mapped_column(Numeric(12, 3), comment="批次级最低库存(遗留, 主用物品级)")
    location: Mapped[str | None] = mapped_column(String(50), comment="存放位置")
    status: Mapped[str] = mapped_column(String(20), default="正常", comment="状态 正常/近效期/停用/损耗")
    barcode: Mapped[str | None] = mapped_column(String(40), unique=True, comment="批次条码(扫码快速录入)")

    item: Mapped["StockItem"] = relationship(back_populates="batches")

    def __repr__(self):
        return f"<StockBatch(item_id={self.item_id}, qty={self.quantity})>"


class StockTransaction(Base):
    """库存流水（替代 inventory_transactions）：入了多少/出了多少/剩余多少全靠它追溯。

    金额语义(带符号便于聚合)：
      - 入库:   unit_cost=进价, cost_amount=+数量*进价(资产增加), revenue_amount=0
      - 出库/发药: unit_cost=所耗批次进价, cost_amount=-数量*进价(COGS),
                  发药另有 unit_price=售价, revenue_amount=+数量*售价(收入)
      - 损耗:   unit_cost=批次进价, cost_amount=-数量*进价(损失, 不计入收入)
      - 盘点:   cost_amount=(实盘-账面)*进价(盘盈正/盘亏负), revenue_amount=0
    因此：期间采购成本=Σ(入库 cost_amount)；期间COGS=Σ(-cost_amount 且为出库，不含损耗/盘点/调整)；
          期间收入=Σ revenue_amount；毛利=收入-COGS；期末库存价值=Σ(批次进价*数量)。
    """
    __tablename__ = "stock_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("stock_items.id", ondelete="CASCADE"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stock_batches.id", ondelete="CASCADE"), comment="关联批次(可为空)")
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="入库/出库/损耗/盘点/调整")
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, comment="变动数量(可正可负)")
    before_quantity: Mapped[float | None] = mapped_column(Numeric(12, 3), comment="变动前(批次数量)")
    after_quantity: Mapped[float | None] = mapped_column(Numeric(12, 3), comment="变动后(批次数量)")
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="单位成本(进价)")
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="单位售价(仅销售/发药)")
    cost_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), comment="成本金额(带符号)")
    revenue_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), comment="收入金额(仅销售/发药)")
    reference_id: Mapped[int | None] = mapped_column(Integer, comment="关联业务ID(处方/采购单/盘点单)")
    reference_type: Mapped[str | None] = mapped_column(String(20), comment="处方/采购/盘点/手动")
    operator: Mapped[str | None] = mapped_column(String(50), comment="操作人")
    note: Mapped[str | None] = mapped_column(Text, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    item: Mapped["StockItem"] = relationship(back_populates="transactions")

    # 报表/流水查询高频按「物品 + 时间」范围检索，复合索引覆盖该类查询
    __table_args__ = (
        Index("ix_stock_transactions_item_created", "item_id", "created_at"),
    )

    def __repr__(self):
        return f"<StockTransaction(item_id={self.item_id}, type='{self.transaction_type}', qty={self.quantity})>"


class Supplier(Base):
    """供应商主数据（用于采购入库自动带价、供应商比价）"""
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="名称")
    contact: Mapped[str | None] = mapped_column(String(50), comment="联系人")
    phone: Mapped[str | None] = mapped_column(String(30), comment="电话")
    address: Mapped[str | None] = mapped_column(String(200), comment="地址")
    note: Mapped[str | None] = mapped_column(Text, comment="备注")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Supplier(id={self.id}, name='{self.name}')>"


class PurchaseOrder(Base):
    """采购单（入库的凭证，自动生成批次与入库流水）"""
    __tablename__ = "purchase_orders"
    # 客户端幂等键落到 order_no 上，由数据库兜底并发重复提交
    __table_args__ = (Index("uq_purchase_orders_order_no", "order_no", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="采购单号")
    supplier_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), comment="供应商")
    supplier_name: Mapped[str | None] = mapped_column(String(100), comment="供应商名称(冗余)")
    order_date: Mapped[str | None] = mapped_column(String(10), comment="采购日期 YYYY-MM-DD")
    note: Mapped[str | None] = mapped_column(Text, comment="备注")
    status: Mapped[str] = mapped_column(String(20), default="已入库", comment="状态 已入库/已作废")
    total_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), comment="采购总金额")
    operator: Mapped[str | None] = mapped_column(String(50), comment="操作人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    items: Mapped[list["PurchaseItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class PurchaseItem(Base):
    """采购单明细（一行对应一个入库批次）"""
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("stock_items.id", ondelete="CASCADE"), nullable=False)
    batch_number: Mapped[str | None] = mapped_column(String(50), comment="批号")
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, comment="数量")
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, comment="进价")
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, comment="金额=数量*进价")
    expiry_date: Mapped[str | None] = mapped_column(String(10), comment="有效期")
    location: Mapped[str | None] = mapped_column(String(50), comment="存放位置")

    order: Mapped["PurchaseOrder"] = relationship(back_populates="items")


class StockOption(Base):
    """库存受控选项（类别 / 单位）：替代前端硬编码与自由文本，统一在界面维护。

    opt_type 区分 category(物品类别) 与 unit(计量单位)；(opt_type, name) 唯一。
    物品类别/单位下拉改为从此表读取，新增类别(如'理疗耗材')或单位不再需要改代码。
    """
    __tablename__ = "stock_options"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    opt_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="类型: category/unit")
    name: Mapped[str] = mapped_column(String(60), nullable=False, comment="选项名称")
    color: Mapped[str | None] = mapped_column(String(20), comment="自定义颜色(HEX)，用于选项标签着色")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("opt_type", "name", name="uq_stock_option_type_name"),
    )

    def __repr__(self):
        return f"<StockOption(id={self.id}, type='{self.opt_type}', name='{self.name}')>"