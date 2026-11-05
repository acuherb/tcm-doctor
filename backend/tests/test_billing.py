"""收费单测试：开具/收款/退费/重复开单/列表筛选。"""
import uuid

from app.database import SessionLocal
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.prescription import Prescription


def _suffix():
    return uuid.uuid4().hex[:8]


def _seed_prescription(db_session, total_price=100.0, status="已审核"):
    s = _suffix()
    patient = Patient(name=f"收费测试患者_{s}")
    db_session.add(patient)
    db_session.commit()
    visit = Visit(patient_id=patient.id, visit_date="2026-01-01", chief_complaint="测试主诉")
    db_session.add(visit)
    db_session.commit()
    pres = Prescription(
        patient_id=patient.id, visit_id=visit.id, status=status,
        doses=2, prescription_type="药方", formula_name="收费测试方",
        total_price=total_price,
    )
    db_session.add(pres)
    db_session.commit()
    return pres.id


def test_create_charge_pending_then_pay(client, db_session, auth_headers):
    pres_id = _seed_prescription(db_session)
    # 开单（待收费）
    r = client.post("/api/v1/billing/charges", json={"prescription_id": pres_id}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "待收费"
    assert float(body["amount"]) == 100.0
    assert float(body["payable"]) == 100.0
    cid = body["id"]
    assert body["charge_no"].startswith("C")

    # 收款
    rp = client.post(
        f"/api/v1/billing/charges/{cid}/pay",
        json={"payment_method": "微信", "paid": 100.0}, headers=auth_headers,
    )
    assert rp.status_code == 200, rp.text
    b2 = rp.json()
    assert b2["status"] == "已收费"
    assert b2["payment_method"] == "微信"
    assert b2["cashier_name"]
    assert b2["paid_at"]


def test_create_charge_with_immediate_payment(client, db_session, auth_headers):
    pres_id = _seed_prescription(db_session, total_price=80.0)
    r = client.post(
        "/api/v1/billing/charges",
        json={"prescription_id": pres_id, "discount": 10.0, "payment_method": "现金", "paid": 70.0},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "已收费"
    assert float(b["discount"]) == 10.0
    assert float(b["payable"]) == 70.0
    assert float(b["paid"]) == 70.0


def test_pay_less_than_payable_rejected(client, db_session, auth_headers):
    pres_id = _seed_prescription(db_session, total_price=50.0)
    r = client.post("/api/v1/billing/charges", json={"prescription_id": pres_id}, headers=auth_headers)
    cid = r.json()["id"]
    rp = client.post(
        f"/api/v1/billing/charges/{cid}/pay",
        json={"payment_method": "现金", "paid": 30.0}, headers=auth_headers,
    )
    assert rp.status_code == 400


def test_refund_paid_charge(client, db_session, auth_headers):
    pres_id = _seed_prescription(db_session)
    r = client.post(
        "/api/v1/billing/charges",
        json={"prescription_id": pres_id, "payment_method": "支付宝", "paid": 100.0},
        headers=auth_headers,
    )
    cid = r.json()["id"]
    rr = client.post(
        f"/api/v1/billing/charges/{cid}/refund",
        json={"reason": "患者退号"}, headers=auth_headers,
    )
    assert rr.status_code == 200, rr.text
    assert rr.json()["status"] == "已退费"
    assert rr.json()["refunded_by"]
    # 退费后不可再收款
    rp = client.post(
        f"/api/v1/billing/charges/{cid}/pay",
        json={"payment_method": "现金", "paid": 100.0}, headers=auth_headers,
    )
    assert rp.status_code == 400


def test_duplicate_pending_charge_returns_same(client, db_session, auth_headers):
    pres_id = _seed_prescription(db_session)
    r1 = client.post("/api/v1/billing/charges", json={"prescription_id": pres_id}, headers=auth_headers)
    r2 = client.post("/api/v1/billing/charges", json={"prescription_id": pres_id}, headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


def test_list_and_filter_charges(client, db_session, auth_headers):
    pres_id = _seed_prescription(db_session)
    client.post(
        "/api/v1/billing/charges",
        json={"prescription_id": pres_id, "payment_method": "现金", "paid": 100.0},
        headers=auth_headers,
    )
    rl = client.get("/api/v1/billing/charges?status=已收费", headers=auth_headers)
    assert rl.status_code == 200, rl.text
    body = rl.json()
    assert body["total"] >= 1
    assert all(c["status"] == "已收费" for c in body["items"])

    rs = client.get("/api/v1/billing/charges/stats/summary", headers=auth_headers)
    assert rs.status_code == 200
    assert rs.json()["paid_amount"] >= 100.0
