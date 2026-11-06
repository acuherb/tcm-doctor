"""模拟旧库升级演练：0023 charges 重建 / 0026 挂号费冲正 / 0027 采购单号唯一。

常规 pytest 用的是「新建库」，这些迁移分支（旧表 NOT NULL、kind=NULL、重复在账单）
根本不会走到，线上升级时才可能暴雷。这里手工构造旧库结构再跑 run_migrations()，
把升级路径固定为可重复执行的回归测试。
"""
from datetime import datetime

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

import app.migrations as mig
from app.models.billing import Charge
from app.models.stock import PurchaseOrder
from app.models.visit import Visit

SCHEMA_MIGRATIONS_DDL = (
    "CREATE TABLE IF NOT EXISTS schema_migrations ("
    "version VARCHAR(50) PRIMARY KEY, description TEXT, applied_at DATETIME)"
)


def _mark_all_applied(conn, except_versions: set[str]) -> None:
    """把除待测迁移外的版本都标记为已执行，让 run_migrations 只跑目标迁移。"""
    conn.execute(text(SCHEMA_MIGRATIONS_DDL))
    for fn in sorted(mig.MIGRATIONS, key=lambda f: f._version):
        if fn._version in except_versions:
            continue
        conn.execute(
            text("INSERT OR IGNORE INTO schema_migrations(version, description, applied_at) "
                 "VALUES (:v, :d, :t)"),
            {"v": fn._version, "d": fn._description, "t": datetime.now()},
        )


def _drop_new_indexes(conn) -> None:
    for name in (
        "uq_charges_prescription_active", "uq_charges_visit_kind_active",
        "uq_purchase_orders_order_no",
    ):
        conn.execute(text(f"DROP INDEX IF EXISTS {name}"))


def _index_names(eng) -> set[str]:
    return {
        idx["name"] for table in inspect(eng).get_table_names()
        for idx in inspect(eng).get_indexes(table)
    }


def test_m0023_rebuilds_legacy_charges(tmp_path, monkeypatch):
    """旧库：prescription_id NOT NULL 且无 kind → sync 补出 NULL 列 → 重建不得中断。"""
    eng = create_engine(f"sqlite:///{tmp_path / 'legacy_0023.db'}")
    Charge.__table__.create(bind=eng)
    with eng.begin() as conn:
        _drop_new_indexes(conn)
        conn.execute(text("ALTER TABLE charges RENAME TO charges_legacy"))
        conn.execute(text(
            "CREATE TABLE charges ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, charge_no VARCHAR(32) NOT NULL, "
            "prescription_id INTEGER NOT NULL, patient_id INTEGER, visit_id INTEGER, "
            "amount NUMERIC(12,2), status VARCHAR(20), created_at DATETIME)"
        ))
        conn.execute(text(
            "INSERT INTO charges (id, charge_no, prescription_id, patient_id, visit_id, "
            "amount, status, created_at) VALUES (1, 'C-LEGACY', 1, 1, 1, 100, '已收费', :t)"
        ), {"t": datetime.now()})
        conn.execute(text("DROP TABLE charges_legacy"))
        _mark_all_applied(conn, {"0023"})

    monkeypatch.setattr(mig, "engine", eng)
    mig.run_migrations()  # 若 COALESCE(kind) 缺失，这里会抛 NOT NULL constraint failed

    cols = {c["name"]: c for c in inspect(eng).get_columns("charges")}
    assert cols["prescription_id"]["nullable"] is True
    assert "kind" in cols and "overpaid" in cols  # 后加的审计列重建时不得丢失
    with eng.connect() as conn:
        assert conn.execute(text("SELECT kind FROM charges WHERE id = 1")).scalar() == "prescription"
        assert conn.execute(text("SELECT COUNT(*) FROM charges WHERE kind IS NULL")).scalar() == 0

    mig.run_migrations()  # 幂等：重复执行不应报错


def test_m0026_m0027_normalizes_legacy_rows(tmp_path, monkeypatch):
    """旧库：重复在账挂号费 / visits.status=NULL / 重复采购单号 → 冲正 + 回填 + 唯一索引。"""
    eng = create_engine(f"sqlite:///{tmp_path / 'legacy_0026.db'}")
    for model in (Charge, Visit, PurchaseOrder):
        model.__table__.create(bind=eng, checkfirst=True)
    with eng.begin() as conn:
        _drop_new_indexes(conn)
    with Session(eng) as s:
        s.add_all([
            Charge(charge_no="REG-1", visit_id=7, kind="挂号费", status="已收费",
                   amount=20, payable=20, paid=20, prescription_id=None),
            Charge(charge_no="REG-2", visit_id=7, kind="挂号费", status="已收费",
                   amount=20, payable=20, paid=20, prescription_id=None),
            Visit(patient_id=1, visit_date="2026-01-01", chief_complaint="迁移演练", status="待诊"),
            PurchaseOrder(order_no="PO-DUP", order_date="2026-01-01"),
            PurchaseOrder(order_no="PO-DUP", order_date="2026-01-01"),
        ])
        s.commit()
    with eng.begin() as conn:
        # 新模型该列为 NOT NULL，用空串模拟「sync 补列后未回填」的旧数据
        conn.execute(text("UPDATE visits SET status = ''"))
        _mark_all_applied(conn, {"0026", "0027"})

    monkeypatch.setattr(mig, "engine", eng)
    mig.run_migrations()

    names = _index_names(eng)
    assert "uq_charges_visit_kind_active" in names
    assert "uq_purchase_orders_order_no" in names
    with eng.connect() as conn:
        active = conn.execute(text(
            "SELECT COUNT(*) FROM charges WHERE visit_id = 7 AND kind = '挂号费' "
            "AND status IN ('待收费','已收费')"
        )).scalar()
        cancelled = conn.execute(text(
            "SELECT COUNT(*) FROM charges WHERE visit_id = 7 AND status = '已取消'"
        )).scalar()
        assert active == 1 and cancelled == 1
        assert conn.execute(text(
            "SELECT COUNT(*) FROM visits WHERE status IS NULL OR status = ''"
        )).scalar() == 0
        assert conn.execute(text("SELECT status FROM visits LIMIT 1")).scalar() == "待诊"
        assert conn.execute(text(
            "SELECT COUNT(*) FROM (SELECT order_no FROM purchase_orders GROUP BY order_no HAVING COUNT(*) > 1)"
        )).scalar() == 0

    mig.run_migrations()  # 幂等
