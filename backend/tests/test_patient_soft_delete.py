"""患者软删除 + 删除守卫测试：
- 有就诊/处方记录的患者禁止删除（返回 400，记录保留），杜绝误删医疗记录与出库孤儿；
- 零记录患者可归档删除（标记 deleted_at，列表默认过滤）。
"""
import uuid

from app.database import SessionLocal
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.prescription import Prescription


def _seed(db_session, with_records=True):
    name = f"软删测试患者_{uuid.uuid4().hex[:8]}"
    patient = Patient(name=name)
    db_session.add(patient)
    db_session.commit()
    if with_records:
        visit = Visit(patient_id=patient.id, visit_date="2026-01-01", chief_complaint="x")
        db_session.add(visit)
        db_session.commit()
        pres = Prescription(
            patient_id=patient.id, visit_id=visit.id, status="已开",
            prescription_type="药方", formula_name="软删测试方",
        )
        db_session.add(pres)
        db_session.commit()
    return patient.id, name


def test_delete_patient_with_records_is_blocked(client, db_session, auth_headers):
    pid, name = _seed(db_session, with_records=True)

    rd = client.delete(f"/api/v1/patients/{pid}", headers=auth_headers)
    assert rd.status_code == 400, rd.text
    assert "不可删除" in rd.json()["detail"]

    # 患者与处方均未被删除（医疗记录保留）
    s = SessionLocal()
    try:
        assert s.get(Patient, pid) is not None
        assert s.get(Patient, pid).deleted_at is None
        assert s.query(Prescription).filter(Prescription.patient_id == pid).count() == 1
    finally:
        s.close()


def test_delete_patient_without_records_is_archived(client, db_session, auth_headers):
    pid, name = _seed(db_session, with_records=False)

    rd = client.delete(f"/api/v1/patients/{pid}", headers=auth_headers)
    assert rd.status_code == 200, rd.text

    s = SessionLocal()
    try:
        p = s.get(Patient, pid)
        assert p is not None
        assert p.deleted_at is not None  # 已归档，未物理删除
    finally:
        s.close()

    # 列表默认过滤已归档患者
    rl = client.get("/api/v1/patients", params={"search": name}, headers=auth_headers)
    assert rl.status_code == 200
    assert name not in {it["name"] for it in rl.json()["items"]}

    # 详情对软删除患者返回 404
    assert client.get(f"/api/v1/patients/{pid}", headers=auth_headers).status_code == 404

    # 归档可见开关可将其找回
    rl2 = client.get(
        "/api/v1/patients", params={"search": name, "include_deleted": True},
        headers=auth_headers,
    )
    assert name in {it["name"] for it in rl2.json()["items"]}
