"""版本化迁移测试（对应 P1-4）：旧库缺列补齐 + 幂等"""
import os
import tempfile
from sqlalchemy import create_engine, text, inspect

from app.database import Base
from app.migrations import run_migrations


def test_migrations_add_missing_columns_and_idempotent():
    # 使用独立引擎，避免污染共享测试库
    import app.database as dbmod
    import app.migrations as migmod

    eng = create_engine(f"sqlite:///{tempfile.mkdtemp()}/iso.db")
    old_db, old_mig = dbmod.engine, migmod.engine
    dbmod.engine, migmod.engine = eng, eng
    try:
        Base.metadata.create_all(bind=eng)
        # 先跑一次，建立 schema_migrations 基线
        run_migrations()
        # 模拟“旧库”缺失新列
        with eng.begin() as c:
            c.execute(text("ALTER TABLE herbs DROP COLUMN flavors"))
            c.execute(text("ALTER TABLE herbs DROP COLUMN aliases"))
            c.execute(text("ALTER TABLE herbs DROP COLUMN price"))
        # 清空版本表，等价于“从未迁移过的旧库”
        with eng.begin() as c:
            c.execute(text("DELETE FROM schema_migrations"))

        run_migrations()
        cols = {x["name"] for x in inspect(eng).get_columns("herbs")}
        assert "flavors" in cols and "aliases" in cols and "price" in cols

        with eng.begin() as c:
            versions = [r[0] for r in c.execute(text("SELECT version FROM schema_migrations")).fetchall()]
        assert sorted(versions) == ["0001", "0002", "0003"]

        # 幂等：重复运行版本数不变
        run_migrations()
        with eng.begin() as c:
            versions2 = [r[0] for r in c.execute(text("SELECT version FROM schema_migrations")).fetchall()]
        assert len(versions2) == 3
    finally:
        dbmod.engine, migmod.engine = old_db, old_mig
