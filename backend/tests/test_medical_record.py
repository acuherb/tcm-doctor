"""按患者导出完整病历端点：聚合完整性、图片开关、HTML 转义与权限。"""
import uuid

from app.models.patient import Patient
from app.models.visit import Visit
from app.models.prescription import Prescription, PrescriptionItem
from app.models.inquiry import InquiryRecord
from app.models.followup import FollowUp
from app.models.followup_reminder import FollowUpReminder
from app.models.user import User
from app.routers.auth import _hash_password


def _seed(db_session):
    patient = Patient(
        name=f"病历导出_{uuid.uuid4().hex[:8]}",
        constitution_type="气虚质",
        constitution_score={"scores": {"气虚质": 60}, "suggestion": "宜健脾"},
        tags=["需复诊"],
    )
    db_session.add(patient)
    db_session.commit()

    visit = Visit(
        patient_id=patient.id, visit_date="2026-01-01", visit_type="初诊",
        chief_complaint="乏力 <b>待排查</b>", tcm_syndrome="脾气虚",
        tongue_image="data:image/png;base64,AAAA",
        lab_report_images=["data:image/png;base64,BBBB"],
    )
    db_session.add(visit)
    db_session.commit()

    rx = Prescription(
        patient_id=patient.id, visit_id=visit.id,
        formula_name="补中益气汤", status="已开",
    )
    db_session.add(rx)
    db_session.commit()
    db_session.add(PrescriptionItem(
        prescription_id=rx.id, herb_name="黄芪", dose=30, is_king_herb=True,
    ))
    db_session.add(InquiryRecord(
        patient_id=patient.id, visit_id=visit.id,
        answers={"q1": "a1"}, notes={"q1": "补充"}, result={"score": 1},
    ))
    db_session.add(FollowUp(
        patient_id=patient.id, visit_id=visit.id,
        followup_date="2026-01-08", improvement="好转", feedback="较前有力",
    ))
    db_session.add(FollowUpReminder(
        patient_id=patient.id, due_date="2026-01-15", status="pending", note="复诊",
    ))
    db_session.commit()
    return patient, visit, rx


def test_export_json_is_complete(client, db_session, auth_headers):
    patient, _, _ = _seed(db_session)
    r = client.get(f"/api/v1/patients/{patient.id}/medical-record", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert "attachment" in r.headers["content-disposition"]

    data = r.json()
    assert data["meta"]["format_version"] == 1
    assert data["patient"]["name"] == patient.name
    assert data["constitution"]["type"] == "气虚质"
    assert data["summary"] == {
        "visits": 1, "prescriptions": 1, "inquiries": 1, "followups": 1, "reminders": 1,
    }
    assert data["unlinked_prescriptions"] == []
    visit = data["visits"][0]
    assert visit["prescriptions"][0]["details"][0]["herb_name"] == "黄芪"
    # 默认不带大体积 base64 图片，但仍标记本次导出口径
    assert "tongue_image" not in visit
    assert visit["image_included"] is False


def test_export_html_escapes_and_images_opt_in(client, db_session, auth_headers):
    patient, _, _ = _seed(db_session)
    url = f"/api/v1/patients/{patient.id}/medical-record"

    with_images = client.get(url, params={"include_images": "true"}, headers=auth_headers)
    assert with_images.status_code == 200
    assert with_images.json()["visits"][0]["tongue_image"].startswith("data:image/")

    html = client.get(
        url, params={"format": "html", "include_images": "true"}, headers=auth_headers,
    )
    assert html.status_code == 200
    assert "text/html" in html.headers["content-type"]
    assert "inline" in html.headers["content-disposition"]
    assert "打印 / 另存为 PDF" in html.text
    # 病历文本中的 HTML 标签必须转义，不能注入到打印页
    assert "&lt;b&gt;待排查&lt;/b&gt;" in html.text
    assert "<b>待排查</b>" not in html.text
    assert "data:image/png;base64,AAAA" in html.text
    assert "黄芪" in html.text and "复诊提醒" in html.text


def test_export_validation_and_permissions(client, db_session, auth_headers):
    patient, _, _ = _seed(db_session)
    url = f"/api/v1/patients/{patient.id}/medical-record"

    assert client.get(url, params={"format": "pdf"}, headers=auth_headers).status_code == 422
    assert client.get("/api/v1/patients/99999999/medical-record", headers=auth_headers).status_code == 404

    # 无 patient:read 的账号不得导出含隐私的完整病历
    user = User(
        username=f"norx_{uuid.uuid4().hex[:8]}",
        password_hash=_hash_password("NoRead123"),
        display_name="无患者读权限",
        is_admin=False,
        role="custom",
        permissions="stock:read",
        must_change_password=False,
    )
    db_session.add(user)
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "NoRead123"},
    )
    assert login.status_code == 200, login.text
    denied = client.get(
        url, headers={"Authorization": f"Bearer {login.json()['token']}"},
    )
    assert denied.status_code == 403
