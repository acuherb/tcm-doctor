"""版本化迁移测试（对应 P1-4）：旧库缺列补齐 + 幂等"""
import os
import tempfile
from sqlalchemy import create_engine, text, inspect

from app.database import Base
from app.migrations import run_migrations, MIGRATIONS


def test_migrations_add_missing_columns_and_idempotent():
    # 使用独立引擎，避免污染共享测试库
    import app.database as dbmod
    import app.migrations as migmod

    eng = create_engine(f"sqlite:///{tempfile.mkdtemp()}/iso.db")
    old_db, old_mig = dbmod.engine, migmod.engine
    dbmod.engine, migmod.engine = eng, eng
    # SessionLocal 也需指向临时引擎，否则 m0002/m0003 会打到共享库而缺表
    old_session = dbmod.SessionLocal
    dbmod.SessionLocal = type(old_session)(bind=eng)
    try:
        Base.metadata.create_all(bind=eng)
        # 先跑一次，建立 schema_migrations 基线
        run_migrations()
        # 模拟“旧库”缺失新列（含 0004 药材多维标签列）
        with eng.begin() as c:
            c.execute(text("ALTER TABLE herbs DROP COLUMN flavors"))
            c.execute(text("ALTER TABLE herbs DROP COLUMN aliases"))
            c.execute(text("ALTER TABLE herbs DROP COLUMN price"))
            c.execute(text("ALTER TABLE herbs DROP COLUMN grade"))
            c.execute(text("ALTER TABLE herbs DROP COLUMN meridians"))
            c.execute(text("ALTER TABLE herbs DROP COLUMN directions"))
            c.execute(text("ALTER TABLE herbs DROP COLUMN tags"))
            c.execute(text("ALTER TABLE herbs DROP COLUMN contraindication"))
        # 清空版本表，等价于“从未迁移过的旧库”
        with eng.begin() as c:
            c.execute(text("DELETE FROM schema_migrations"))

        run_migrations()
        cols = {x["name"] for x in inspect(eng).get_columns("herbs")}
        # 0001 补齐的列
        assert "flavors" in cols and "aliases" in cols and "price" in cols
        # 0004 补齐的药材多维标签列
        assert {"grade", "meridians", "directions", "tags", "contraindication"} <= cols

        with eng.begin() as c:
            versions = [r[0] for r in c.execute(text("SELECT version FROM schema_migrations")).fetchall()]
        # 动态断言：覆盖当前全部编号迁移（避免硬编码版本号随迁移增长而失效）
        expected_versions = sorted(fn._version for fn in MIGRATIONS)
        assert sorted(versions) == expected_versions

        # 幂等：重复运行版本数不变
        run_migrations()
        with eng.begin() as c:
            versions2 = [r[0] for r in c.execute(text("SELECT version FROM schema_migrations")).fetchall()]
        assert len(versions2) == len(MIGRATIONS)
    finally:
        dbmod.engine, migmod.engine = old_db, old_mig
        dbmod.SessionLocal = old_session


def test_m0006_migrates_herb_inventory_idempotently():
    """m0006 把旧 herb_inventory/inventory_transactions 迁移进 stock 表后删除旧表；
    重复执行（含「数据已落库但旧表仍在」的崩溃恢复场景）不得产生重复库存数据。"""
    import app.database as dbmod
    import app.migrations as migmod
    from app.database import Base, SessionLocal

    eng = create_engine(f"sqlite:///{tempfile.mkdtemp()}/m0006.db")
    old_db, old_mig = dbmod.engine, migmod.engine
    dbmod.engine, migmod.engine = eng, eng
    old_session = dbmod.SessionLocal
    dbmod.SessionLocal = type(old_session)(bind=eng)
    try:
        # 用模型建全量新表（含 herbs/stock_*，但不含已废弃的 herb_inventory）
        import app.models  # 触发全部模型注册到 Base.metadata，确保 create_all 能建表
        Base.metadata.create_all(bind=eng)
        # 通过 ORM 写入 herbs，自动应用 ORM 默认值（避免裸 SQL 漏填 NOT NULL 列）
        from app.models.herb import Herb

        sdb = dbmod.SessionLocal()
        sdb.add_all([
            Herb(name='黄芪', grade='选', price=12.0, min_stock=10.0, toxicity='无毒'),
            Herb(name='当归', grade='选', price=20.0, min_stock=5.0, toxicity='无毒'),
        ])
        sdb.commit()
        sdb.close()
        with eng.begin() as c:
            c.execute(text(
                "CREATE TABLE herb_inventory (id INTEGER PRIMARY KEY, herb_id INTEGER, "
                "batch_number TEXT, quantity REAL, unit_price REAL, sale_price REAL, "
                "purchase_date TEXT, expiry_date TEXT, supplier TEXT, min_stock REAL, "
                "location TEXT, status TEXT)"
            ))
            c.execute(text(
                "CREATE TABLE inventory_transactions (herb_id INTEGER, transaction_type TEXT, "
                "quantity REAL, before_quantity REAL, after_quantity REAL, reference_id TEXT, "
                "note TEXT, operator TEXT, created_at TEXT)"
            ))
            c.execute(text(
                "INSERT INTO herb_inventory (id,herb_id,batch_number,quantity,unit_price,sale_price) "
                "VALUES (10,1,'B1',100,8,12),(11,2,'B2',50,15,20)"
            ))
            c.execute(text(
                "INSERT INTO inventory_transactions "
                "(herb_id,transaction_type,quantity,before_quantity,after_quantity,operator) "
                "VALUES (1,'入库',100,0,100,'admin')"
            ))
        from app.migrations import m0006
        m0006()
        with eng.begin() as c:
            si = c.execute(text("SELECT count(*) FROM stock_items")).fetchone()[0]
            sb = c.execute(text("SELECT count(*) FROM stock_batches")).fetchone()[0]
            tx = c.execute(text("SELECT count(*) FROM stock_transactions")).fetchone()[0]
            dropped = c.execute(text(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='herb_inventory'"
            )).fetchone()[0]
        assert (si, sb, tx, dropped) == (2, 2, 1, 0), (si, sb, tx, dropped)

        # 幂等：旧表已删，再跑一次不应重复造数
        m0006()
        with eng.begin() as c:
            si2 = c.execute(text("SELECT count(*) FROM stock_items")).fetchone()[0]
        assert si2 == 2

        # 崩溃恢复场景：旧表被「重新放回」且含已迁移过的 herb（模拟 commit 后 DROP 前崩溃），
        # 护栏应复用已有 StockItem，不再重复创建
        with eng.begin() as c:
            c.execute(text(
                "CREATE TABLE herb_inventory (id INTEGER PRIMARY KEY, herb_id INTEGER, "
                "batch_number TEXT, quantity REAL, unit_price REAL, sale_price REAL, "
                "purchase_date TEXT, expiry_date TEXT, supplier TEXT, min_stock REAL, "
                "location TEXT, status TEXT)"
            ))
            c.execute(text(
                "INSERT INTO herb_inventory (id,herb_id,batch_number,quantity,unit_price,sale_price) "
                "VALUES (10,1,'B1',100,8,12)"
            ))
        m0006()
        with eng.begin() as c:
            si3 = c.execute(text("SELECT count(*) FROM stock_items")).fetchone()[0]
            dropped3 = c.execute(text(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='herb_inventory'"
            )).fetchone()[0]
        assert si3 == 2 and dropped3 == 0, (si3, dropped3)
    finally:
        dbmod.engine, migmod.engine = old_db, old_mig
        dbmod.SessionLocal = old_session
