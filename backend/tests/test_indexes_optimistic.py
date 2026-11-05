"""迁移 0018：高频查询索引 + 乐观锁 version 列的一致性验证。"""
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm.exc import StaleDataError

from app.database import SessionLocal
from app.models.patient import Patient


def test_indexes_created(client, db_session):
    insp = sa_inspect(db_session.bind)
    names = lambda t: {i["name"] for i in insp.get_indexes(t)}
    assert "idx_visits_patient_date" in names("visits")
    assert "idx_prescriptions_patient" in names("prescriptions")
    assert "idx_prescriptions_visit" in names("prescriptions")
    assert "idx_followups_patient" in names("followups")
    assert "idx_followups_visit" in names("followups")
    assert "idx_inquiry_patient" in names("inquiry_records")
    assert "idx_inquiry_visit" in names("inquiry_records")
    assert "idx_conversations_patient" in names("conversations")
    assert "idx_conversations_last_msg" in names("conversations")
    assert "idx_patients_deleted_at" in names("patients")


def test_version_columns_exist(client, db_session):
    insp = sa_inspect(db_session.bind)
    for t in ("patients", "visits", "prescriptions", "followups"):
        cols = {c["name"] for c in insp.get_columns(t)}
        assert "version" in cols


def test_optimistic_lock_normal_update(client):
    db = SessionLocal()
    try:
        p = Patient(name="乐观锁正常改")
        db.add(p)
        db.commit()
        v0 = p.version
        p.name = "改名后"
        db.commit()
        assert p.version == v0 + 1
    finally:
        db.close()


def test_optimistic_lock_conflict(client):
    db = SessionLocal()
    try:
        p = Patient(name="乐观锁冲突")
        db.add(p)
        db.commit()
        pid = p.id
    finally:
        db.close()

    s1, s2 = SessionLocal(), SessionLocal()
    try:
        a = s1.get(Patient, pid)
        b = s2.get(Patient, pid)
        a.name = "A 先改"
        s1.commit()          # version 1 -> 2
        b.name = "B 后改"
        raised = False
        try:
            s2.commit()      # WHERE version=1，但库已是 2 -> 冲突
        except StaleDataError:
            raised = True
            s2.rollback()
        assert raised
    finally:
        s1.close()
        s2.close()
