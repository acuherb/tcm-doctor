"""「一处方一笔在账的钱」：收费幂等、全链路联动与状态机回归测试。

覆盖用户报告的「处方列表点一次收费后还能继续重复收费」，以及由此展开的
作废/删除/编辑/退号联动、就诊状态机、迁移 0025 冲正与部分唯一索引。
"""
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.billing import Charge
from app.models.herb import Herb
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.visit import Visit


def _suffix():
    return uuid.uuid4().hex[:8]


def _seed(db_session, total_price=None):
    """建患者/就诊/处方，返回构造 PUT 所需的全部 id。"""
    s = _suffix()
    p = Patient(name=f"幂等患者_{s}")
    db_session.add(p)
    db_session.commit()
    v = Visit(patient_id=p.id, visit_date="2026-01-01", chief_complaint="幂等测试")
    db_session.add(v)
    db_session.commit()
    h = Herb(name=f"幂等药材_{s}", nature="平")
    db_session.add(h)
    db_session.commit()
    pres = Prescription(
        patient_id=p.id, visit_id=v.id, status="已审核", doses=2,
        prescription_type="药方", formula_name="幂等方", total_price=total_price,
    )
    db_session.add(pres)
    db_session.commit()
    return {
        "pres_id": pres.id, "visit_id": v.id, "patient_id": p.id,
        "herb_id": h.id, "herb_name": h.name,
    }


def _put_payload(d, doctor_notes="医嘱", price=None):
    item = {"herb_id": d["herb_id"], "herb_name": d["herb_name"], "dose": 10.0}
    if price is not None:
        item["price"] = price
    return {
        "visit_id": d["visit_id"], "patient_id": d["patient_id"],
        "doses": 2, "formula_name": "幂等方", "prescription_type": "药方",
        "doctor_notes": doctor_notes, "items": [item],
    }


def _active_count(db_session, pres_id):
    return db_session.query(Charge).filter(
        Charge.prescription_id == pres_id,
        Charge.status.in_(("待收费", "已收费")),
    ).count()


# ── P0：重复收费根治 ──

def test_repeated_charge_returns_same_charge(client, db_session, auth_headers):
    """用户报告症状：连续两次「开单即收」只能产生一张单、营收不翻倍。"""
    d = _seed(db_session, total_price=100.0)
    payload = {"prescription_id": d["pres_id"], "payment_method": "现金", "paid": 100.0}

    r1 = client.post("/api/v1/billing/charges", json=payload, headers=auth_headers)
    r2 = client.post("/api/v1/billing/charges", json=payload, headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["status"] == "已收费"
    assert _active_count(db_session, d["pres_id"]) == 1
    assert db_session.query(Charge).filter(Charge.prescription_id == d["pres_id"]).count() == 1


def test_repeated_charge_does_not_double_revenue(client, db_session, auth_headers):
    d = _seed(db_session, total_price=100.0)
    before = client.get("/api/v1/billing/charges/stats/summary", headers=auth_headers).json()
    payload = {"prescription_id": d["pres_id"], "payment_method": "微信", "paid": 100.0}
    for _ in range(3):
        assert client.post("/api/v1/billing/charges", json=payload, headers=auth_headers).status_code == 200
    after = client.get("/api/v1/billing/charges/stats/summary", headers=auth_headers).json()
    assert abs((after["collected_amount"] - before["collected_amount"]) - 100.0) < 0.01
    assert abs((after["paid_amount"] - before["paid_amount"]) - 100.0) < 0.01


def test_reuse_pending_charge_completes_payment(client, db_session, auth_headers):
    """先开单（待收费），再从处方列表「收费」→ 复用同一张单并完成收款。"""
    d = _seed(db_session, total_price=60.0)
    r0 = client.post("/api/v1/billing/charges", json={"prescription_id": d["pres_id"]}, headers=auth_headers)
    assert r0.json()["status"] == "待收费"
    cid = r0.json()["id"]

    r = client.post("/api/v1/billing/charges", json={
        "prescription_id": d["pres_id"], "payment_method": "现金", "paid": 60.0,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == cid
    assert r.json()["status"] == "已收费"
    assert _active_count(db_session, d["pres_id"]) == 1


def test_refunded_or_cancelled_charge_allows_new_charge(client, db_session, auth_headers):
    """已退费/已取消是终态历史，不占用唯一性：可合法重新开单收费。"""
    d = _seed(db_session, total_price=50.0)
    c1 = client.post("/api/v1/billing/charges", json={
        "prescription_id": d["pres_id"], "payment_method": "现金", "paid": 50.0,
    }, headers=auth_headers).json()
    assert client.post(f"/api/v1/billing/charges/{c1['id']}/refund",
                       json={"reason": "患者退药"}, headers=auth_headers).status_code == 200
    c2 = client.post("/api/v1/billing/charges", json={
        "prescription_id": d["pres_id"], "payment_method": "现金", "paid": 50.0,
    }, headers=auth_headers)
    assert c2.status_code == 200, c2.text
    c2body = c2.json()
    assert c2body["id"] != c1["id"]
    assert c2body["status"] == "已收费"
    assert _active_count(db_session, d["pres_id"]) == 1

    assert client.post(f"/api/v1/billing/charges/{c2body['id']}/cancel",
                       json={"reason": "已收费不可作废"}, headers=auth_headers).status_code == 400
    # 待收费单作废后也可重开
    d2 = _seed(db_session, total_price=20.0)
    c3 = client.post("/api/v1/billing/charges", json={"prescription_id": d2["pres_id"]},
                     headers=auth_headers).json()
    assert client.post(f"/api/v1/billing/charges/{c3['id']}/cancel",
                       json={"reason": "金额录错"}, headers=auth_headers).status_code == 200
    c4 = client.post("/api/v1/billing/charges", json={"prescription_id": d2["pres_id"]},
                     headers=auth_headers)
    assert c4.status_code == 200 and c4.json()["id"] != c3["id"]


def test_unique_index_blocks_second_active_charge(db_session):
    """数据库兜底：直接插入第二张在账单会被部分唯一索引拒绝。"""
    d = _seed(db_session, total_price=30.0)
    s = SessionLocal()
    try:
        c = Charge(charge_no=f"C-IDX-{_suffix()}", prescription_id=d["pres_id"],
                   kind="prescription", amount=30, payable=30, status="待收费")
        s.add(c)
        s.commit()
        s.add(Charge(charge_no=f"C-IDX2-{_suffix()}", prescription_id=d["pres_id"],
                     kind="prescription", amount=30, payable=30, status="已收费"))
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        # 终态历史不占用唯一性
        s.add(Charge(charge_no=f"C-IDX3-{_suffix()}", prescription_id=d["pres_id"],
                     kind="prescription", amount=30, payable=30, status="已退费"))
        s.commit()
    finally:
        s.close()


def test_concurrent_charges_converge_to_one_active(client, db_session, auth_headers):
    """两个前台同时点收费：最终只有一笔在账，不产生重复单。"""
    d = _seed(db_session, total_price=80.0)
    payload = {"prescription_id": d["pres_id"], "payment_method": "现金", "paid": 80.0}
    with ThreadPoolExecutor(max_workers=2) as ex:
        results = list(ex.map(
            lambda _: client.post("/api/v1/billing/charges", json=payload, headers=auth_headers),
            range(2),
        ))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert len({r.json()["id"] for r in results}) == 1
    assert _active_count(db_session, d["pres_id"]) == 1


def test_prescription_list_exposes_charge_status(client, db_session, auth_headers):
    """列表回填收费状态，前端才有依据收敛按钮。"""
    d = _seed(db_session, total_price=40.0)
    rows = client.get("/api/v1/prescriptions", params={"limit": 200}, headers=auth_headers).json()
    mine = next(r for r in rows if r["id"] == d["pres_id"])
    assert mine["charge_status"] is None
    c = client.post("/api/v1/billing/charges", json={
        "prescription_id": d["pres_id"], "payment_method": "现金", "paid": 40.0,
    }, headers=auth_headers).json()
    rows = client.get("/api/v1/prescriptions", params={"limit": 200}, headers=auth_headers).json()
    mine = next(r for r in rows if r["id"] == d["pres_id"])
    assert mine["charge_id"] == c["id"]
    assert mine["charge_status"] == "已收费"


# ── 全链路联动 ──

def test_void_prescription_auto_refunds(client, db_session, auth_headers):
    """作废已收费处方 → 自动全额退费，钱不留在账上。"""
    d = _seed(db_session, total_price=100.0)
    c = client.post("/api/v1/billing/charges", json={
        "prescription_id": d["pres_id"], "payment_method": "现金", "paid": 100.0,
    }, headers=auth_headers).json()
    r = client.post(f"/api/v1/prescriptions/{d['pres_id']}/void", headers=auth_headers)
    assert r.status_code == 200, r.text
    ch = client.get(f"/api/v1/billing/charges/{c['id']}", headers=auth_headers).json()
    assert ch["status"] == "已退费"
    assert float(ch["refund_amount"]) == 100.0
    assert float(ch["net_paid"]) == 0.0
    # 幂等：重复作废不再触发第二次退费
    assert client.post(f"/api/v1/prescriptions/{d['pres_id']}/void", headers=auth_headers).status_code == 200


def test_void_prescription_cancels_pending_charge(client, db_session, auth_headers):
    d = _seed(db_session, total_price=100.0)
    c = client.post("/api/v1/billing/charges", json={"prescription_id": d["pres_id"]},
                    headers=auth_headers).json()
    assert client.post(f"/api/v1/prescriptions/{d['pres_id']}/void", headers=auth_headers).status_code == 200
    ch = client.get(f"/api/v1/billing/charges/{c['id']}", headers=auth_headers).json()
    assert ch["status"] == "已取消"


def test_delete_charged_prescription_rejected(client, db_session, auth_headers):
    """已收费处方不可物理删除，引导走「作废」（保留审计链）。"""
    d = _seed(db_session, total_price=100.0)
    client.post("/api/v1/billing/charges", json={
        "prescription_id": d["pres_id"], "payment_method": "现金", "paid": 100.0,
    }, headers=auth_headers)
    r = client.delete(f"/api/v1/prescriptions/{d['pres_id']}", headers=auth_headers)
    assert r.status_code == 400
    assert "已收费" in r.json()["detail"]


def test_delete_prescription_cancels_pending_charge(client, db_session, auth_headers):
    d = _seed(db_session, total_price=100.0)
    c = client.post("/api/v1/billing/charges", json={"prescription_id": d["pres_id"]},
                    headers=auth_headers).json()
    assert client.delete(f"/api/v1/prescriptions/{d['pres_id']}", headers=auth_headers).status_code == 200
    db_session.expire_all()
    ch = db_session.get(Charge, c["id"])
    assert ch.status == "已取消"


def test_edit_charged_prescription_freezes_amount(client, db_session, auth_headers):
    """已收费处方改金额被拒，改医嘱/备注仍允许。"""
    d = _seed(db_session, total_price=100.0)
    client.post("/api/v1/billing/charges", json={
        "prescription_id": d["pres_id"], "payment_method": "现金", "paid": 100.0,
    }, headers=auth_headers)
    r = client.put(f"/api/v1/prescriptions/{d['pres_id']}",
                   json=_put_payload(d, price=10.0), headers=auth_headers)
    assert r.status_code == 400
    assert "金额不可修改" in r.json()["detail"]

    # total_price 不变的处方：改医嘱放行
    d2 = _seed(db_session, total_price=None)
    client.post("/api/v1/billing/charges", json={
        "prescription_id": d2["pres_id"], "payment_method": "现金", "paid": 0.0,
    }, headers=auth_headers)
    r2 = client.put(f"/api/v1/prescriptions/{d2['pres_id']}",
                    json=_put_payload(d2, doctor_notes="忌辛辣"), headers=auth_headers)
    assert r2.status_code == 200, r2.text


def test_cancel_visit_settles_all_charges(client, db_session, auth_headers):
    """退号结算覆盖该就诊下全部收费单（挂号费 + 处方收费）。"""
    d = _seed(db_session, total_price=100.0)
    c = client.post("/api/v1/billing/charges", json={
        "prescription_id": d["pres_id"], "payment_method": "现金", "paid": 100.0,
    }, headers=auth_headers).json()
    r = client.patch(f"/api/v1/registration/{d['visit_id']}",
                     json={"status": "已取消"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    ch = client.get(f"/api/v1/billing/charges/{c['id']}", headers=auth_headers).json()
    assert ch["status"] == "已退费"
    assert float(ch["net_paid"]) == 0.0


def test_visit_state_machine_rejects_backwards_transition(client, db_session, auth_headers):
    s = _suffix()
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"状态机_{s}"}, "registration_fee": 0,
    }, headers=auth_headers)
    vid = r.json()["visit"]["id"]
    pid = r.json()["visit"]["patient_id"]
    assert client.post(f"/api/v1/registration/{vid}/call", headers=auth_headers).status_code == 200
    # 完成就诊需先留下真实病历
    assert client.put(f"/api/v1/patients/{pid}/visits/{vid}", json={
        "chief_complaint": "头痛两日", "palpation": "脉弦",
    }, headers=auth_headers).status_code == 200
    assert client.post(f"/api/v1/registration/{vid}/complete", headers=auth_headers).status_code == 200
    # 已完成是终态，不可回跳到已取消（否则会二次触发退挂号费）
    bad = client.patch(f"/api/v1/registration/{vid}", json={"status": "已取消"}, headers=auth_headers)
    assert bad.status_code == 400
    assert "不可从" in bad.json()["detail"]


# ── 迁移 0025 ──

def test_partial_unique_index_exists():
    insp = inspect(SessionLocal().bind)
    names = {i["name"] for i in insp.get_indexes("charges")}
    assert "uq_charges_prescription_active" in names


def test_m0025_cleans_duplicates_and_builds_index(tmp_path):
    """存量库：重复在账单自动冲正（保留最早一张、留痕），并建立唯一索引。"""
    import app.migrations as mig
    from app.migrations import m0025

    eng = create_engine(f"sqlite:///{tmp_path / 'legacy25.db'}")
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE charges("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, charge_no VARCHAR(32), "
            "prescription_id INTEGER, visit_id INTEGER, kind VARCHAR(20), "
            "status VARCHAR(20), note TEXT, cancel_reason VARCHAR(200), "
            "cancelled_by VARCHAR(50), cancelled_at DATETIME)"
        ))
        c.execute(text("INSERT INTO charges(charge_no,prescription_id,kind,status) "
                       "VALUES('C1', 7, 'prescription', '已收费')"))
        c.execute(text("INSERT INTO charges(charge_no,prescription_id,kind,status) "
                       "VALUES('C2', 7, 'prescription', '已收费')"))
        c.execute(text("INSERT INTO charges(charge_no,prescription_id,kind,status) "
                       "VALUES('C3', 8, 'prescription', '待收费')"))
        c.execute(text("INSERT INTO charges(charge_no,prescription_id,kind,status) "
                       "VALUES('C4', 8, NULL, '已收费')"))

    old_engine = mig.engine
    mig.engine = eng
    try:
        m0025()
        with eng.begin() as c:
            assert c.execute(text(
                "SELECT COUNT(*) FROM charges WHERE prescription_id=7 AND status IN ('待收费','已收费')"
            )).scalar() == 1
            assert c.execute(text(
                "SELECT COUNT(*) FROM charges WHERE prescription_id=8 AND status IN ('待收费','已收费')"
            )).scalar() == 1
            assert "冲正" in c.execute(text("SELECT note FROM charges WHERE charge_no='C2'")).scalar()
            with pytest.raises(IntegrityError):
                c.execute(text("INSERT INTO charges(charge_no,prescription_id,kind,status) "
                               "VALUES('C5', 7, 'prescription', '待收费')"))
    finally:
        mig.engine = old_engine
