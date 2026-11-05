"""针对收费/挂号 code review（P0/P1/P2）修复的回归测试。

覆盖：退款金额落库与统计口径、超收记录、部分退费、作废待收费单、退号联动退费、
同日重复挂号、挂号费幂等、单号并发重试、服务层事务边界、排队号唯一约束。
"""
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.billing import Charge
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.visit import Visit


def _suffix():
    return uuid.uuid4().hex[:8]


def _seed_visit(db_session):
    s = _suffix()
    p = Patient(name=f"复核患者_{s}")
    db_session.add(p)
    db_session.commit()
    v = Visit(patient_id=p.id, visit_date="2026-01-01", chief_complaint="复核用就诊")
    db_session.add(v)
    db_session.commit()
    return p, v


def _seed_prescription(db_session, total_price=100.0):
    p, v = _seed_visit(db_session)
    pres = Prescription(
        patient_id=p.id, visit_id=v.id, status="已审核", doses=2,
        prescription_type="药方", formula_name="复核方", total_price=total_price,
    )
    db_session.add(pres)
    db_session.commit()
    return pres.id


# ── P0 ──

def test_refund_records_actual_amount_and_stats_are_consistent(client, db_session, auth_headers):
    """超收 150/应付 100 全额退：实退=150、净营收不凭空多 50，且原因必填。"""
    pres_id = _seed_prescription(db_session, total_price=100.0)
    before = client.get("/api/v1/billing/charges/stats/summary", headers=auth_headers).json()

    r = client.post("/api/v1/billing/charges",
                    json={"prescription_id": pres_id, "payment_method": "现金", "paid": 150.0},
                    headers=auth_headers)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert float(r.json()["overpaid"]) == 50.0
    assert "多收未找零" in (r.json()["note"] or "")

    # 缺原因 -> 422
    no_reason = client.post(f"/api/v1/billing/charges/{cid}/refund", json={}, headers=auth_headers)
    assert no_reason.status_code == 422

    rr = client.post(f"/api/v1/billing/charges/{cid}/refund",
                     json={"reason": "患者退号"}, headers=auth_headers)
    assert rr.status_code == 200, rr.text
    b = rr.json()
    assert b["status"] == "已退费"
    assert float(b["refund_amount"]) == 150.0   # 实退落库，按 paid 而非 payable
    assert float(b["paid"]) == 150.0            # paid 保留审计轨迹
    assert float(b["net_paid"]) == 0.0          # 净收为 0，不再像收过钱
    assert b["refund_reason"] == "患者退号"

    after = client.get("/api/v1/billing/charges/stats/summary", headers=auth_headers).json()
    # 收款与退款同为实收口径：累计实收 - 实退 = 净营收，永远对得上账
    assert abs(after["net_amount"] - (after["collected_amount"] - after["refunded_amount"])) < 0.01
    assert abs((after["refunded_amount"] - before["refunded_amount"]) - 150.0) < 0.01
    assert abs((after["collected_amount"] - before["collected_amount"]) - 150.0) < 0.01
    assert abs(after["paid_amount"] - before["paid_amount"]) < 0.01  # 已退不再计入已收
    assert after["overpaid_amount"] - before["overpaid_amount"] >= 50.0


def test_partial_refund_and_over_refund_rejected(client, db_session, auth_headers):
    pres_id = _seed_prescription(db_session, total_price=100.0)
    cid = client.post("/api/v1/billing/charges",
                      json={"prescription_id": pres_id, "payment_method": "现金", "paid": 100.0},
                      headers=auth_headers).json()["id"]

    too_much = client.post(f"/api/v1/billing/charges/{cid}/refund",
                           json={"reason": "多退", "refund_amount": 120.0}, headers=auth_headers)
    assert too_much.status_code == 400

    partial = client.post(f"/api/v1/billing/charges/{cid}/refund",
                          json={"reason": "部分退药", "refund_amount": 40.0}, headers=auth_headers)
    assert partial.status_code == 200, partial.text
    b = partial.json()
    assert float(b["refund_amount"]) == 40.0
    assert float(b["net_paid"]) == 60.0
    assert "部分退费" in (b["note"] or "")


def test_pay_records_overpaid(client, db_session, auth_headers):
    """收款接口（非开单即收）同样记录多收差额。"""
    pres_id = _seed_prescription(db_session, total_price=60.0)
    cid = client.post("/api/v1/billing/charges",
                      json={"prescription_id": pres_id}, headers=auth_headers).json()["id"]
    r = client.post(f"/api/v1/billing/charges/{cid}/pay",
                    json={"payment_method": "现金", "paid": 80.0}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert float(r.json()["overpaid"]) == 20.0
    assert "多收未找零" in (r.json()["note"] or "")


# ── P2 ──

def test_cancel_pending_charge(client, db_session, auth_headers):
    """开错单可作废，不再污染待收费列表。"""
    pres_id = _seed_prescription(db_session)
    cid = client.post("/api/v1/billing/charges",
                      json={"prescription_id": pres_id}, headers=auth_headers).json()["id"]
    assert client.post(f"/api/v1/billing/charges/{cid}/cancel",
                       json={}, headers=auth_headers).status_code == 422  # 原因必填
    r = client.post(f"/api/v1/billing/charges/{cid}/cancel",
                    json={"reason": "金额录错"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "已取消"
    assert r.json()["cancel_reason"] == "金额录错"
    # 作废后不可再收款
    assert client.post(f"/api/v1/billing/charges/{cid}/pay",
                       json={"payment_method": "现金", "paid": 100.0},
                       headers=auth_headers).status_code == 400


def test_cancel_visit_refunds_registration_fee(client, db_session, auth_headers):
    """退号自动全额退已收挂号费，钱不留在账上。"""
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"退号_{_suffix()}"},
        "registration_fee": 30.0, "payment_method": "微信", "paid": 30.0,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    vid, cid = r.json()["visit"]["id"], r.json()["charge"]["id"]

    c = client.patch(f"/api/v1/registration/{vid}", json={"status": "已取消"}, headers=auth_headers)
    assert c.status_code == 200, c.text
    ch = client.get(f"/api/v1/billing/charges/{cid}", headers=auth_headers).json()
    assert ch["status"] == "已退费"
    assert float(ch["refund_amount"]) == 30.0
    assert float(ch["net_paid"]) == 0.0


def test_cancel_visit_voids_pending_registration_fee(client, db_session, auth_headers):
    """待收挂号费在退号时自动作废。"""
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"待收退号_{_suffix()}"},
        "registration_fee": 10.0,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    vid, cid = r.json()["visit"]["id"], r.json()["charge"]["id"]
    assert r.json()["charge"]["status"] == "待收费"

    client.patch(f"/api/v1/registration/{vid}", json={"status": "已取消"}, headers=auth_headers)
    ch = client.get(f"/api/v1/billing/charges/{cid}", headers=auth_headers).json()
    assert ch["status"] == "已取消"


def test_same_day_duplicate_registration_blocked_unless_forced(client, db_session, auth_headers):
    s = _suffix()
    p = Patient(name=f"同日_{s}")
    db_session.add(p)
    db_session.commit()
    payload = {"patient_id": p.id, "registration_fee": 0}

    r1 = client.post("/api/v1/registration", json=payload, headers=auth_headers)
    assert r1.status_code == 200, r1.text
    r2 = client.post("/api/v1/registration", json=payload, headers=auth_headers)
    assert r2.status_code == 409
    assert "今日已挂号" in r2.json()["detail"]

    r3 = client.post("/api/v1/registration", json={**payload, "force": True}, headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["visit"]["id"] != r1.json()["visit"]["id"]


def test_non_prescription_charge_is_idempotent_by_visit(client, db_session, auth_headers):
    """同一就诊 + 同类型的待收费单复用，接口重试不重复开单。"""
    _, v = _seed_visit(db_session)
    payload = {"kind": "registration", "visit_id": v.id, "amount": 15.0,
               "title": "挂号费", "patient_name": "测试"}
    r1 = client.post("/api/v1/billing/charges", json=payload, headers=auth_headers)
    r2 = client.post("/api/v1/billing/charges", json=payload, headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


# ── P1 ──

def test_create_charge_commit_false_keeps_transaction_boundary(db_session):
    """服务层 commit=False 只 flush，调用方回滚可整体撤销。"""
    from app.schemas.billing import ChargeCreate
    from app.services.billing_service import create_charge

    _, v = _seed_visit(db_session)
    with SessionLocal() as s:
        before = s.query(Charge).filter(Charge.visit_id == v.id).count()
        create_charge(s, ChargeCreate(kind="registration", visit_id=v.id, amount=9.0,
                                      title="挂号费", patient_name="测试"), commit=False)
        s.rollback()
        assert s.query(Charge).filter(Charge.visit_id == v.id).count() == before


def test_charge_no_collision_retries_once(monkeypatch, db_session):
    """单号撞唯一约束时经 SAVEPOINT 回滚并重取号，不影响外层事务。"""
    import app.services.billing_service as svc
    from app.schemas.billing import ChargeCreate

    _, v = _seed_visit(db_session)
    s = SessionLocal()
    try:
        existing_no = f"C-COLLIDE-{_suffix()}"
        s.add(Charge(charge_no=existing_no, visit_id=v.id, kind="registration",
                     amount=5.0, payable=5.0, status="待收费"))
        s.commit()
        fresh_no = f"C-FRESH-{_suffix()}"
        seq = iter([existing_no, fresh_no, fresh_no])
        monkeypatch.setattr(svc, "generate_charge_no", lambda _db: next(seq))

        c = svc.create_charge(s, ChargeCreate(kind="prescription", visit_id=v.id,
                                              amount=7.0, title="自费项", patient_name="测试"))
        assert c.charge_no == fresh_no
        assert s.query(Charge).filter(Charge.charge_no == fresh_no).count() == 1
    finally:
        s.close()


def test_queue_no_unique_index_exists():
    """(visit_date, queue_no) 唯一索引兜底并发重号。"""
    from sqlalchemy import inspect
    from app.database import engine

    insp = inspect(engine)
    uniques = {tuple(i["column_names"]) for i in insp.get_indexes("visits") if i.get("unique")}
    constraints = {tuple(c["column_names"]) for c in insp.get_unique_constraints("visits")}
    assert ("visit_date", "queue_no") in uniques | constraints


def test_m0023_rebuild_tolerates_columns_added_by_sync(tmp_path):
    """_sync_model_columns 会先补齐新列，m0023 重建 charges 时不能引用新表不存在的列。"""
    import app.migrations as mig
    from app.migrations import m0023, m0024

    db_file = tmp_path / "legacy23_sync.db"
    eng = create_engine(f"sqlite:///{db_file}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE prescriptions(id INTEGER PRIMARY KEY)"))
        c.execute(text("CREATE TABLE visits(id INTEGER PRIMARY KEY, visit_date VARCHAR(20), queue_no INTEGER)"))
        c.execute(text(
            "CREATE TABLE charges("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, charge_no VARCHAR(32) NOT NULL, "
            "prescription_id INTEGER NOT NULL, patient_id INTEGER, visit_id INTEGER, "
            "patient_name VARCHAR(50), prescription_title VARCHAR(120), amount NUMERIC(12,2), "
            "discount NUMERIC(12,2), payable NUMERIC(12,2), paid NUMERIC(12,2), "
            "payment_method VARCHAR(20), status VARCHAR(20), cashier_id INTEGER, "
            "cashier_name VARCHAR(50), paid_at DATETIME, refunded_by VARCHAR(50), "
            "refunded_at DATETIME, refund_reason VARCHAR(200), note TEXT, created_at DATETIME, "
            "kind VARCHAR(20) NOT NULL DEFAULT 'prescription', "
            "overpaid NUMERIC(12,2), refund_amount NUMERIC(12,2), "
            "cancelled_by VARCHAR(50), cancelled_at DATETIME, cancel_reason VARCHAR(200))"
        ))
        c.execute(text(
            "INSERT INTO charges(charge_no,prescription_id,amount,status) "
            "VALUES('C-SYNC', 1, 12.0, '待收费')"
        ))

    old_engine = mig.engine
    mig.engine = eng
    try:
        m0023()
        m0024()
        with eng.begin() as c:
            assert c.execute(text("SELECT charge_no FROM charges WHERE charge_no='C-SYNC'")).fetchone()
            assert c.execute(text(
                "INSERT INTO charges(charge_no,patient_id,status,kind) VALUES('C-NEW',1,'待收费','registration')"
            ))
    finally:
        mig.engine = old_engine


def test_m0024_backfills_refund_and_adds_unique_index(tmp_path):
    """存量库：补列、按实收回填退款额、清理重复排队号并建唯一索引。"""
    import app.migrations as mig
    from app.migrations import m0024

    db_file = tmp_path / "legacy24.db"
    eng = create_engine(f"sqlite:///{db_file}")
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE visits(id INTEGER PRIMARY KEY, visit_date VARCHAR(20), queue_no INTEGER, status VARCHAR(20))"
        ))
        c.execute(text("INSERT INTO visits VALUES(1, '2026-01-01', 1, '待诊')"))
        c.execute(text("INSERT INTO visits VALUES(2, '2026-01-01', 1, '待诊')"))  # 历史重号
        c.execute(text(
            "CREATE TABLE charges(id INTEGER PRIMARY KEY, charge_no VARCHAR(32), paid NUMERIC(12,2), "
            "payable NUMERIC(12,2), status VARCHAR(20))"
        ))
        c.execute(text("INSERT INTO charges VALUES(1, 'C-OLD', 120.0, 100.0, '已退费')"))
        c.execute(text("INSERT INTO charges VALUES(2, 'C-PAID', 150.0, 100.0, '已收费')"))

    old_engine = mig.engine
    mig.engine = eng
    try:
        m0024()
        with eng.begin() as c:
            cols = {r[1] for r in c.execute(text("PRAGMA table_info(charges)"))}
            assert {"overpaid", "refund_amount", "cancelled_by", "cancelled_at", "cancel_reason"} <= cols
            old = c.execute(text("SELECT refund_amount FROM charges WHERE id=1")).scalar()
            assert float(old) == 120.0
            assert float(c.execute(text("SELECT overpaid FROM charges WHERE id=2")).scalar()) == 50.0
            # 重号已被重排
            assert c.execute(text("SELECT COUNT(DISTINCT queue_no) FROM visits")).scalar() == 2
            with pytest.raises(IntegrityError):
                c.execute(text("INSERT INTO visits VALUES(3, '2026-01-01', 1, '待诊')"))
    finally:
        mig.engine = old_engine
