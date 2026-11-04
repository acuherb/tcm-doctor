"""处方数据完整性：就诊必须属于所选患者（避免处方挂到别的患者就诊）。"""
import uuid

from app.database import SessionLocal
from app.models.herb import Herb
from app.models.stock import StockItem, StockBatch
from app.models.patient import Patient
from app.models.visit import Visit


def _seed_two(db_session):
    s = uuid.uuid4().hex[:8]
    p1 = Patient(name=f"完整测试患者1_{s}")
    p2 = Patient(name=f"完整测试患者2_{s}")
    db_session.add_all([p1, p2])
    db_session.commit()
    v1 = Visit(patient_id=p1.id, visit_date="2026-01-01", chief_complaint="v1")
    v2 = Visit(patient_id=p2.id, visit_date="2026-01-02", chief_complaint="v2")
    db_session.add_all([v1, v2])
    db_session.commit()
    herb = Herb(name=f"完整测试药材_{s}", nature="平")
    db_session.add(herb)
    db_session.commit()
    item = StockItem(item_type="中药", name=f"完整测试药材_{s}", unit="g", herb_id=herb.id, is_active=True)
    db_session.add(item)
    db_session.commit()
    batch = StockBatch(item_id=item.id, status="正常", quantity=100.0, batch_number=f"BV1_{s}", unit_price=5.0)
    db_session.add(batch)
    db_session.commit()
    return p1.id, v1.id, p2.id, v2.id, herb.id, batch.id, s


def _item(herb_id, batch_id, suffix):
    return [{"herb_id": herb_id, "herb_name": f"完整测试药材_{suffix}", "dose": 10, "inventory_id": batch_id}]


def test_create_prescription_rejects_mismatched_visit(client, db_session, auth_headers):
    p1, v1, p2, v2, herb_id, batch_id, s = _seed_two(db_session)
    payload = {
        "patient_id": p1, "visit_id": v2, "formula_name": "错挂测试",
        "prescription_type": "药方", "doses": 7, "preparation_method": "水煎服",
        "items": _item(herb_id, batch_id, s),
    }
    r = client.post("/api/v1/prescriptions", json=payload, headers=auth_headers)
    assert r.status_code == 400, r.text
    assert "不属于该患者" in r.json()["detail"]


def test_update_prescription_rejects_mismatched_visit(client, db_session, auth_headers):
    p1, v1, p2, v2, herb_id, batch_id, s = _seed_two(db_session)
    # 先建一张归属 p1/v1 的合法处方
    create = client.post("/api/v1/prescriptions", json={
        "patient_id": p1, "visit_id": v1, "formula_name": "合法方",
        "prescription_type": "药方", "doses": 7, "preparation_method": "水煎服",
        "items": _item(herb_id, batch_id, s),
    }, headers=auth_headers)
    assert create.status_code == 200, create.text
    rx_id = create.json()["id"]
    # 改成 p2 患者但保留 v1 就诊（属于 p1）→ 应被拒绝
    bad = client.put(f"/api/v1/prescriptions/{rx_id}", json={
        "patient_id": p2, "visit_id": v1, "formula_name": "合法方",
        "prescription_type": "药方", "doses": 7, "preparation_method": "水煎服",
        "items": _item(herb_id, batch_id, s),
    }, headers=auth_headers)
    assert bad.status_code == 400, bad.text
    assert "不属于该患者" in bad.json()["detail"]
