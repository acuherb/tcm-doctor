"""发药扣库存测试（对应 P0-2：并发双扣修复 + 不可重复发药）"""
from app.database import SessionLocal
from app.models.herb import Herb, HerbInventory
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.prescription import Prescription, PrescriptionItem


def _fresh_qty(inv_id):
    s = SessionLocal()
    try:
        return s.get(HerbInventory, inv_id).quantity
    finally:
        s.close()


def _seed_prescription(db_session):
    patient = Patient(name="发药测试患者")
    db_session.add(patient)
    db_session.commit()

    visit = Visit(
        patient_id=patient.id, visit_date="2026-01-01", chief_complaint="测试主诉"
    )
    db_session.add(visit)
    db_session.commit()

    herb = Herb(name="发药测试药材", nature="平")
    db_session.add(herb)
    db_session.commit()

    inv = HerbInventory(
        herb_id=herb.id, status="正常", quantity=100.0, batch_number="B1"
    )
    db_session.add(inv)
    db_session.commit()

    pres = Prescription(
        patient_id=patient.id,
        visit_id=visit.id,
        status="已审核",
        doses=2,
        prescription_type="药方",
        formula_name="发药测试方",
    )
    db_session.add(pres)
    db_session.commit()

    item = PrescriptionItem(
        prescription_id=pres.id,
        herb_id=herb.id,
        herb_name="发药测试药材",
        dose=10.0,
    )
    db_session.add(item)
    db_session.commit()
    return pres.id, inv.id


def test_dispense_deducts_and_prevents_double(client, db_session, auth_headers):
    pres_id, inv_id = _seed_prescription(db_session)
    before = _fresh_qty(inv_id)

    # 第一次发药：扣减 dose(10) * doses(2) = 20
    r1 = client.put(
        f"/api/v1/prescriptions/{pres_id}/dispense", headers=auth_headers
    )
    assert r1.status_code == 200, r1.text
    after_first = _fresh_qty(inv_id)
    assert float(after_first) == float(before) - 20.0

    # 第二次发药（状态已为“已发药”）：应被拒绝，库存不再变化
    r2 = client.put(
        f"/api/v1/prescriptions/{pres_id}/dispense", headers=auth_headers
    )
    assert r2.status_code == 400, r2.text
    after_second = _fresh_qty(inv_id)
    assert float(after_second) == float(after_first)
