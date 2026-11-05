"""处方电子签名与防篡改：哈希基线、签名、编辑失效、篡改检出。"""
import uuid

from app.database import SessionLocal
from app.models.herb import Herb
from app.models.stock import StockItem, StockBatch
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.prescription import Prescription, PrescriptionItem, compute_prescription_hash


def _suffix():
    return uuid.uuid4().hex[:8]


def _seed(db_session):
    s = _suffix()
    patient = Patient(name=f"签名测试患者_{s}")
    db_session.add(patient)
    db_session.commit()
    visit = Visit(patient_id=patient.id, visit_date="2026-01-01", chief_complaint="测试主诉")
    db_session.add(visit)
    db_session.commit()
    herb = Herb(name=f"签名测试药材_{s}", nature="平")
    db_session.add(herb)
    db_session.commit()
    item = StockItem(item_type="中药", name=f"签名测试药材_{s}", unit="g", herb_id=herb.id, is_active=True, sell_price=10.0)
    db_session.add(item)
    db_session.commit()
    batch = StockBatch(item_id=item.id, status="正常", quantity=100.0, batch_number=f"B1_{s}", unit_price=5.0)
    db_session.add(batch)
    db_session.commit()
    pres = Prescription(patient_id=patient.id, visit_id=visit.id, status="已开", doses=2, prescription_type="药方", formula_name="签名测试方")
    db_session.add(pres)
    db_session.commit()
    pit = PrescriptionItem(prescription_id=pres.id, herb_id=herb.id, herb_name=f"签名测试药材_{s}", dose=10.0, inventory_id=batch.id)
    db_session.add(pit)
    db_session.commit()
    return {
        "pres_id": pres.id, "patient_id": patient.id, "visit_id": visit.id,
        "herb_id": herb.id, "herb_name": f"签名测试药材_{s}", "batch_id": batch.id,
    }


def test_hash_stable_and_changes_with_content(client):
    s = SessionLocal()
    try:
        d = _seed(s)
        p = s.get(Prescription, d["pres_id"])
        h1 = compute_prescription_hash(p)
        assert len(h1) == 64
        # 同内容稳定
        assert compute_prescription_hash(p) == h1
        # 改临床内容 → 哈希变化
        p.formula_name = "改名后的方"
        h2 = compute_prescription_hash(p)
        assert h2 != h1
    finally:
        s.close()


def test_sign_sets_baseline_and_valid(client, db_session, auth_headers):
    d = _seed(db_session)
    # 签名前：未签名
    r0 = client.get(f"/api/v1/prescriptions/{d['pres_id']}/verify")
    assert r0.status_code == 200
    assert r0.json()["signed"] is False
    assert r0.json()["tampered"] is False  # 基线为空，不误报

    # 签名
    r = client.post(f"/api/v1/prescriptions/{d['pres_id']}/sign", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signed"] is True
    assert body["signature_valid"] is True
    assert body["tampered"] is False
    assert body["signed_by"]
    assert body["content_hash"]

    # verify 端点一致
    rv = client.get(f"/api/v1/prescriptions/{d['pres_id']}/verify")
    assert rv.json()["signed"] is True
    assert rv.json()["signature_valid"] is True
    assert rv.json()["tampered"] is False
    assert rv.json()["stored_hash"] == rv.json()["computed_hash"]


def test_edit_after_sign_clears_signature(client, db_session, auth_headers):
    d = _seed(db_session)
    client.post(f"/api/v1/prescriptions/{d['pres_id']}/sign", headers=auth_headers)
    # 编辑处方（改剂量），应使签名失效
    payload = {
        "visit_id": d["visit_id"], "patient_id": d["patient_id"],
        "formula_name": "签名测试方", "prescription_type": "药方", "doses": 3,
        "items": [{"herb_id": d["herb_id"], "herb_name": d["herb_name"], "dose": 15.0, "inventory_id": d["batch_id"]}],
        "acupoints": [], "injections": [],
    }
    r = client.put(f"/api/v1/prescriptions/{d['pres_id']}", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signed"] is False
    assert body["signature_valid"] is False
    assert body["content_hash"]  # 已重算基线


def test_tamper_detected_after_sign(client, db_session, auth_headers):
    d = _seed(db_session)
    client.post(f"/api/v1/prescriptions/{d['pres_id']}/sign", headers=auth_headers)
    # 模拟外部篡改：直接改库内临床字段（绕过签名逻辑，不动 content_hash/signature）
    s = SessionLocal()
    try:
        p = s.get(Prescription, d["pres_id"])
        p.formula_name = "被篡改的方名"
        s.commit()
    finally:
        s.close()
    rv = client.get(f"/api/v1/prescriptions/{d['pres_id']}/verify")
    j = rv.json()
    assert j["tampered"] is True                 # 当前内容 ≠ 基线
    assert j["signed"] is True                    # 签名令牌仍在
    assert j["signature_valid"] is True           # 令牌仍匹配其签署时的基线
    assert j["computed_hash"] != j["stored_hash"]


def test_sign_rejects_cancelled(client, db_session, auth_headers):
    d = _seed(db_session)
    s = SessionLocal()
    try:
        s.get(Prescription, d["pres_id"]).status = "已取消"
        s.commit()
    finally:
        s.close()
    r = client.post(f"/api/v1/prescriptions/{d['pres_id']}/sign", headers=auth_headers)
    assert r.status_code == 400
