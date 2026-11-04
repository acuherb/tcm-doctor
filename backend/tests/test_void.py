"""作废处方（冲红）测试：已发药作废应回补库存并生成冲红流水；未发药作废仅改状态。"""
import uuid

from app.database import SessionLocal
from app.models.herb import Herb
from app.models.stock import StockItem, StockBatch, StockTransaction
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.prescription import Prescription, PrescriptionItem


def _suffix():
    return uuid.uuid4().hex[:8]


def _seed_prescription(db_session, status="已审核"):
    s = _suffix()
    patient = Patient(name=f"作废测试患者_{s}")
    db_session.add(patient)
    db_session.commit()

    visit = Visit(patient_id=patient.id, visit_date="2026-01-01", chief_complaint="测试主诉")
    db_session.add(visit)
    db_session.commit()

    herb = Herb(name=f"作废测试药材_{s}", nature="平")
    db_session.add(herb)
    db_session.commit()

    item = StockItem(item_type="中药", name=f"作废测试药材_{s}", unit="g", herb_id=herb.id, is_active=True, sell_price=10.0)
    db_session.add(item)
    db_session.commit()

    batch = StockBatch(item_id=item.id, status="正常", quantity=100.0, batch_number=f"B1_{s}", unit_price=5.0)
    db_session.add(batch)
    db_session.commit()

    pres = Prescription(
        patient_id=patient.id, visit_id=visit.id, status=status,
        doses=2, prescription_type="药方", formula_name="作废测试方",
    )
    db_session.add(pres)
    db_session.commit()

    pit = PrescriptionItem(
        prescription_id=pres.id, herb_id=herb.id, herb_name=f"作废测试药材_{s}",
        dose=10.0, inventory_id=batch.id,
    )
    db_session.add(pit)
    db_session.commit()
    return pres.id, batch.id


def _batch_qty(batch_id):
    s = SessionLocal()
    try:
        return s.get(StockBatch, batch_id).quantity
    finally:
        s.close()


def _void_txn_count(pres_id):
    s = SessionLocal()
    try:
        return s.query(StockTransaction).filter(
            StockTransaction.reference_type == "处方",
            StockTransaction.reference_id == pres_id,
            StockTransaction.transaction_type == "冲红",
        ).count()
    finally:
        s.close()


def test_void_dispensed_restores_stock_and_makes_reversing_txn(client, db_session, auth_headers):
    pres_id, batch_id = _seed_prescription(db_session)
    before = _batch_qty(batch_id)

    # 发药：扣 10*2=20
    r1 = client.put(f"/api/v1/prescriptions/{pres_id}/dispense", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    assert float(_batch_qty(batch_id)) == float(before) - 20.0

    # 作废（默认 return_stock=True）：应回补库存 + 生成冲红流水
    rv = client.post(f"/api/v1/prescriptions/{pres_id}/void", headers=auth_headers)
    assert rv.status_code == 200, rv.text
    assert rv.json()["status"] == "已取消"
    # 库存回到发药前
    assert float(_batch_qty(batch_id)) == float(before)
    # 生成了一条冲红流水
    assert _void_txn_count(pres_id) == 1
    s = SessionLocal()
    try:
        t = s.query(StockTransaction).filter(
            StockTransaction.reference_type == "处方",
            StockTransaction.reference_id == pres_id,
            StockTransaction.transaction_type == "冲红",
        ).first()
        assert t is not None
        assert float(t.quantity) == 20.0
        assert t.revenue_amount is not None and t.revenue_amount < 0   # 退款，冲减收入
        assert t.cost_amount is not None and t.cost_amount > 0          # 货退回，冲减 COGS
    finally:
        s.close()


def test_void_dispensed_no_return_stock_keeps_stock(client, db_session, auth_headers):
    pres_id, batch_id = _seed_prescription(db_session)
    before = _batch_qty(batch_id)

    r1 = client.put(f"/api/v1/prescriptions/{pres_id}/dispense", headers=auth_headers)
    assert r1.status_code == 200
    assert float(_batch_qty(batch_id)) == float(before) - 20.0

    # 作废但不退回库存
    rv = client.post(
        f"/api/v1/prescriptions/{pres_id}/void",
        params={"return_stock": False}, headers=auth_headers,
    )
    assert rv.status_code == 200
    assert rv.json()["status"] == "已取消"
    # 库存不回补（药已消耗/未退）
    assert float(_batch_qty(batch_id)) == float(before) - 20.0
    # 不生成冲红流水
    assert _void_txn_count(pres_id) == 0


def test_void_not_dispensed_only_changes_status(client, db_session, auth_headers):
    pres_id, batch_id = _seed_prescription(db_session, status="已开")
    before = _batch_qty(batch_id)

    rv = client.post(f"/api/v1/prescriptions/{pres_id}/void", headers=auth_headers)
    assert rv.status_code == 200
    assert rv.json()["status"] == "已取消"
    # 未发药：库存无变化，无冲红流水
    assert float(_batch_qty(batch_id)) == float(before)
    assert _void_txn_count(pres_id) == 0
