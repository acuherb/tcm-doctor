"""患者软删除测试：删除仅归档（标记 deleted_at），医疗记录保留，列表默认过滤。"""
from app.database import SessionLocal
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.prescription import Prescription


def _seed(db_session):
    patient = Patient(name="软删测试患者")
    db_session.add(patient)
    db_session.commit()
    visit = Visit(patient_id=patient.id, visit_date="2026-01-01", chief_complaint="x")
    db_session.add(visit)
    db_session.commit()
    pres = Prescription(
        patient_id=patient.id, visit_id=visit.id, status="已开",
        prescription_type="药方", formula_name="软删测试方",
    )
    db_session.add(pres)
    db_session.commit()
    return patient.id, pres.id


def test_delete_patient_soft_deletes_and_keeps_records(client, db_session, auth_headers):
    pid, pres_id = _seed(db_session)

    # 删除 → 仅归档
    rd = client.delete(f"/api/v1/patients/{pid}", headers=auth_headers)
    assert rd.status_code == 200, rd.text

    s = SessionLocal()
    try:
        p = s.get(Patient, pid)
        assert p is not None
        assert p.deleted_at is not None            # 已标记删除
        # 处方 / 就诊等医疗记录保留（不再被物理删除）
        assert s.get(Prescription, pres_id) is not None
    finally:
        s.close()

    # 列表默认过滤已归档患者
    rl = client.get("/api/v1/patients", params={"search": "软删测试患者"}, headers=auth_headers)
    assert rl.status_code == 200
    names = {it["name"] for it in rl.json()["items"]}
    assert "软删测试患者" not in names

    # 详情对软删除患者返回 404
    rg = client.get(f"/api/v1/patients/{pid}", headers=auth_headers)
    assert rg.status_code == 404

    # 归档可见开关可将其找回
    rl2 = client.get(
        "/api/v1/patients", params={"search": "软删测试患者", "include_deleted": True},
        headers=auth_headers,
    )
    names2 = {it["name"] for it in rl2.json()["items"]}
    assert "软删测试患者" in names2
