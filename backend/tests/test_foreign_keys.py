"""外键约束（PRAGMA + ondelete 级联）验证"""
from sqlalchemy import text

from app.database import SessionLocal
from app.models.stock import StockItem, StockBatch


def test_foreign_keys_pragma_enabled():
    db = SessionLocal()
    try:
        # PRAGMA foreign_keys 应在连接时由 database.py 的监听器开启
        assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
    finally:
        db.close()


def test_stock_item_delete_cascades_batches():
    """删除物品应级联删除其批次（验证 ondelete=CASCADE 在 DB 层生效）。"""
    db = SessionLocal()
    try:
        item = StockItem(name="级联测试物品")
        db.add(item)
        db.flush()
        db.add(StockBatch(item_id=item.id, quantity=1))
        db.commit()

        db.delete(item)
        db.commit()

        assert db.query(StockBatch).filter(StockBatch.item_id == item.id).count() == 0
    finally:
        db.close()
