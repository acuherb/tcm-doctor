"""AI 辨证读既往疗效：summarize_prior_history 与 analyze 的既往注入。"""
import asyncio
import uuid

from app.models.patient import Patient
from app.models.visit import Visit
from app.models.followup import FollowUp
from app.medical_record import summarize_prior_history
from app.services.ai_diagnosis_service import diagnosis_service


def _seed(db_session):
    patient = Patient(name=f"复诊对比_{uuid.uuid4().hex[:8]}", constitution_type="气虚质")
    db_session.add(patient)
    db_session.commit()
    visit = Visit(
        patient_id=patient.id, visit_date="2026-01-01", visit_type="初诊",
        chief_complaint="乏力", tcm_disease="虚劳", tcm_syndrome="脾气虚",
        treatment_method="健脾益气",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.add(FollowUp(
        patient_id=patient.id, visit_id=visit.id,
        followup_date="2026-01-08", improvement="好转", feedback="较前有力",
    ))
    db_session.commit()
    return patient, visit


def test_summarize_prior_history_includes_visit_and_followup():
    record = {
        "visits": [{
            "visit_date": "2026-01-01", "visit_type": "初诊", "chief_complaint": "乏力",
            "tcm_disease": "虚劳", "tcm_syndrome": "脾气虚", "treatment_method": "健脾",
            "ai_analysis": "脾肺气虚，宜补益",
            "prescriptions": [{"formula_name": "补中益气汤", "details": [
                {"category": "prescription_items", "herb_name": "黄芪", "dose": "30g"},
            ]}],
        }],
        "followups": [{"followup_date": "2026-01-08", "improvement": "好转", "feedback": "较前有力"}],
    }
    txt = summarize_prior_history(record)
    assert "既往病史与疗效回顾" in txt
    assert "脾气虚" in txt
    assert "补中益气汤" in txt
    assert "黄芪" in txt
    assert "好转" in txt


def test_summarize_prior_history_empty():
    assert summarize_prior_history({"visits": [], "followups": []}) == ""


def test_analyze_injects_prior_history(client, db_session):
    from app.config import settings
    patient, _ = _seed(db_session)
    # 强制走本地规则辨证分支（无 API Key），使断言确定、不依赖外部 LLM
    old = settings.deepseek_api_key
    settings.deepseek_api_key = None
    try:
        result = asyncio.run(diagnosis_service.analyze(
            chief_complaint="仍觉乏力", patient_id=patient.id, db=db_session,
        ))
    finally:
        settings.deepseek_api_key = old
    assert "既往病史与疗效回顾" in result["syndrome_analysis"]
    assert "脾气虚" in result["syndrome_analysis"]
    assert "好转" in result["syndrome_analysis"]


def test_analyze_without_patient_id_has_no_prior(client, db_session):
    from app.config import settings
    old = settings.deepseek_api_key
    settings.deepseek_api_key = None
    try:
        result = asyncio.run(diagnosis_service.analyze(
            chief_complaint="乏力", patient_id=None, db=db_session,
        ))
    finally:
        settings.deepseek_api_key = old
    assert "既往病史与疗效回顾" not in result["syndrome_analysis"]
