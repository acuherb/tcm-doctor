"""删处方回归测试：删除处方须级联清理其自动生成的随访提醒（M4）。"""
from app.database import SessionLocal
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.prescription import Prescription
from app.models.followup_reminder import FollowUpReminder


def _seed_prescription_with_reminder(db_session):
    patient = Patient(name="删处方测试患者")
    db_session.add(patient)
    db_session.commit()

    visit = Visit(patient_id=patient.id, visit_date="2026-01-01", chief_complaint="测试")
    db_session.add(visit)
    db_session.commit()

    pres = Prescription(
        patient_id=patient.id,
        visit_id=visit.id,
        status="已开",
        prescription_type="药方",
        formula_name="删处方测试方",
    )
    db_session.add(pres)
    db_session.commit()

    db_session.add(
        FollowUpReminder(
            patient_id=patient.id,
            due_date="2026-02-01",
            source_type="prescription",
            source_id=pres.id,
            note="疗程结束回访",
        )
    )
    db_session.commit()
    return pres.id, patient.id


def test_delete_prescription_cleans_its_reminders(client, db_session, auth_headers):
    pres_id, _ = _seed_prescription_with_reminder(db_session)

    # 删处方前：该处方来源的提醒应存在
    assert (
        db_session.query(FollowUpReminder)
        .filter(
            FollowUpReminder.source_type == "prescription",
            FollowUpReminder.source_id == pres_id,
        )
        .count()
        == 1
    )

    r = client.delete(f"/api/v1/prescriptions/{pres_id}", headers=auth_headers)
    assert r.status_code == 200, r.text

    s = SessionLocal()
    try:
        # 处方本身已删
        assert s.query(Prescription).filter(Prescription.id == pres_id).count() == 0
        # 其随访提醒一并清理（不再指向已删处方的死链）
        assert (
            s.query(FollowUpReminder)
            .filter(
                FollowUpReminder.source_type == "prescription",
                FollowUpReminder.source_id == pres_id,
            )
            .count()
            == 0
        )
    finally:
        s.close()
