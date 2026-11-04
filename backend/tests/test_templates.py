"""模板导入的回归测试：幂等 upsert + dry_run 预检不落库"""
from app.database import Base, engine
from app.templates import import_items
from app.models.herb import Herb

# 本模块直接使用 db_session fixture，不经过 app 启动，需自行建表
Base.metadata.create_all(bind=engine)


def test_import_items_idempotent(db_session):
    items = [
        {"name": "QA草药甲", "efficacy": "x"},
        {"name": "QA草药乙", "efficacy": "y"},
    ]
    r1 = import_items(db_session, "herbs", items)
    assert r1["added"] == 2 and r1["updated"] == 0, r1
    # 再次导入相同内容应全部计为更新、无新增
    r2 = import_items(db_session, "herbs", items)
    assert r2["added"] == 0 and r2["updated"] == 2, r2
    # 修改已存在条目后导入应计为更新
    r3 = import_items(db_session, "herbs", [{"name": "QA草药甲", "efficacy": "z"}])
    assert r3["updated"] == 1 and r3["added"] == 0, r3


def test_import_items_dry_run_no_commit(db_session):
    items = [{"name": "QA草药DryRun", "efficacy": "x"}]
    pre = import_items(db_session, "herbs", items, dry_run=True)
    assert pre["added"] == 1, pre
    # 预检不应写入数据库
    assert db_session.query(Herb).filter(Herb.name == "QA草药DryRun").count() == 0
    # 正式导入后才落库
    real = import_items(db_session, "herbs", items)
    assert real["added"] == 1, real
    assert db_session.query(Herb).filter(Herb.name == "QA草药DryRun").count() == 1


def test_import_items_skips_malformed(db_session):
    items = [
        {"name": "QA草药良", "efficacy": "x"},
        "不是字典",                # 非 dict，跳过
        {"efficacy": "缺名字"},     # 缺自然键，跳过
    ]
    r = import_items(db_session, "herbs", items)
    assert r["added"] == 1, r
    assert r["skipped"] == 2, r
