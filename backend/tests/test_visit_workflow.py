"""就诊状态由业务事实驱动的回归测试。

覆盖：挂号占位病历 → 完善病历自动推进「已接诊」→ 有依据才能「完成」；
以及误点「接诊/完成」后的受控撤销与审计日志。
"""
import uuid

from app.database import SessionLocal
from app.models.log import OperationLog
from app.models.prescription import Prescription


def _suffix():
    return uuid.uuid4().hex[:8]


def _register(client, auth_headers, fee=0):
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"就诊流程_{_suffix()}"},
        "registration_fee": fee,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    b = r.json()
    return b["visit"]["id"], b["visit"]["patient_id"]


def _write_record(client, auth_headers, pid, vid, **extra):
    payload = {"chief_complaint": "胃脘胀痛3天", "inquiry": "纳差、夜寐差"}
    payload.update(extra)
    return client.put(f"/api/v1/patients/{pid}/visits/{vid}", json=payload, headers=auth_headers)


def _queue_item(client, auth_headers, vid):
    items = client.get("/api/v1/registration/queue", headers=auth_headers).json()["items"]
    return next(i for i in items if i["id"] == vid)


def test_placeholder_visit_cannot_be_completed(client, db_session, auth_headers):
    """挂号产生的占位病历，不能凭两次点击就变成「已完成」。"""
    vid, pid = _register(client, auth_headers)
    mine = _queue_item(client, auth_headers, vid)
    assert mine["status"] == "待诊"
    assert mine["evidence"]["has_record"] is False
    assert mine["evidence"]["can_complete"] is False
    assert mine["evidence"]["completion_blockers"]

    assert client.post(f"/api/v1/registration/{vid}/call", headers=auth_headers).status_code == 200
    blocked = client.post(f"/api/v1/registration/{vid}/complete", headers=auth_headers)
    assert blocked.status_code == 400
    assert "无法完成就诊" in blocked.json()["detail"]
    assert _queue_item(client, auth_headers, vid)["status"] == "已接诊"  # 未被误置为已完成


def test_saving_record_auto_advances_to_in_consultation(client, db_session, auth_headers):
    """医生写病历这一业务事实本身就能把「待诊」推进为「已接诊」，不靠手动点。"""
    vid, pid = _register(client, auth_headers)
    r = _write_record(client, auth_headers, pid, vid)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "已接诊"
    assert _queue_item(client, auth_headers, vid)["status"] == "已接诊"
    assert _queue_item(client, auth_headers, vid)["evidence"]["can_complete"] is True


def test_complete_requires_real_record(client, db_session, auth_headers):
    vid, pid = _register(client, auth_headers)
    assert client.post(f"/api/v1/registration/{vid}/call", headers=auth_headers).status_code == 200
    assert client.post(f"/api/v1/registration/{vid}/complete", headers=auth_headers).status_code == 400
    assert _write_record(client, auth_headers, pid, vid).status_code == 200
    done = client.post(f"/api/v1/registration/{vid}/complete", headers=auth_headers)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "已完成"


def test_only_complaint_without_any_detail_is_not_a_record(client, db_session, auth_headers):
    """只改主诉、没有任何四诊/诊断内容，仍不算真实诊疗记录。"""
    vid, pid = _register(client, auth_headers)
    client.post(f"/api/v1/registration/{vid}/call", headers=auth_headers)
    r = client.put(f"/api/v1/patients/{pid}/visits/{vid}",
                   json={"chief_complaint": "头痛"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "已接诊"  # 已是已接诊，状态不变
    assert _queue_item(client, auth_headers, vid)["evidence"]["has_record"] is False
    assert client.post(f"/api/v1/registration/{vid}/complete", headers=auth_headers).status_code == 400


# ── 误点补救 ──

def test_revert_wrong_call_back_to_waiting(client, db_session, auth_headers):
    vid, _ = _register(client, auth_headers)
    assert client.post(f"/api/v1/registration/{vid}/call", headers=auth_headers).status_code == 200
    assert _queue_item(client, auth_headers, vid)["evidence"]["can_revert"] is True

    assert client.post(f"/api/v1/registration/{vid}/revert",
                       json={}, headers=auth_headers).status_code == 422  # 原因必填
    rev = client.post(f"/api/v1/registration/{vid}/revert",
                      json={"reason": "叫号点错，患者还没进来"}, headers=auth_headers)
    assert rev.status_code == 200, rev.text
    assert rev.json()["status"] == "待诊"


def test_revert_wrong_complete_back_to_in_consultation(client, db_session, auth_headers):
    vid, pid = _register(client, auth_headers)
    client.post(f"/api/v1/registration/{vid}/call", headers=auth_headers)
    assert _write_record(client, auth_headers, pid, vid).status_code == 200
    assert client.post(f"/api/v1/registration/{vid}/complete", headers=auth_headers).status_code == 200

    rev = client.post(f"/api/v1/registration/{vid}/revert",
                      json={"reason": "误点完成，还有检查未录入"}, headers=auth_headers)
    assert rev.status_code == 200, rev.text
    assert rev.json()["status"] == "已接诊"
    assert _queue_item(client, auth_headers, vid)["evidence"]["can_complete"] is True


def test_revert_refused_after_payment_or_dispensing(client, db_session, auth_headers):
    """钱和药一动就不允许回退，避免账实不符；只能走作废/退费重开。"""
    vid, pid = _register(client, auth_headers)
    client.post(f"/api/v1/registration/{vid}/call", headers=auth_headers)
    assert _write_record(client, auth_headers, pid, vid).status_code == 200
    pres = Prescription(
        patient_id=pid, visit_id=vid, status="已审核", doses=2,
        prescription_type="药方", formula_name="回退测试方", total_price=100.0,
    )
    db_session.add(pres)
    db_session.commit()
    assert client.post("/api/v1/billing/charges", json={
        "prescription_id": pres.id, "payment_method": "现金", "paid": 100.0,
    }, headers=auth_headers).status_code == 200
    assert client.post(f"/api/v1/registration/{vid}/complete", headers=auth_headers).status_code == 200

    ev = _queue_item(client, auth_headers, vid)["evidence"]
    assert ev["paid_prescriptions"] == 1
    assert ev["can_revert"] is False
    rev = client.post(f"/api/v1/registration/{vid}/revert",
                      json={"reason": "试图撤销已收费就诊"}, headers=auth_headers)
    assert rev.status_code == 400
    assert "不可撤销" in rev.json()["detail"]


def test_revert_refused_once_record_written(client, db_session, auth_headers):
    """已写病历的「已接诊」不能撤回待诊（那会抹掉已开始诊疗的事实）。"""
    vid, pid = _register(client, auth_headers)
    assert _write_record(client, auth_headers, pid, vid).status_code == 200
    assert _queue_item(client, auth_headers, vid)["evidence"]["can_revert"] is False
    rev = client.post(f"/api/v1/registration/{vid}/revert",
                      json={"reason": "想撤回"}, headers=auth_headers)
    assert rev.status_code == 400


def test_revert_writes_operation_log(client, db_session, auth_headers):
    """每次撤销都留审计痕迹：操作人、状态变化、原因。"""
    vid, _ = _register(client, auth_headers)
    client.post(f"/api/v1/registration/{vid}/call", headers=auth_headers)
    reason = f"审计验证_{_suffix()}"
    assert client.post(f"/api/v1/registration/{vid}/revert",
                       json={"reason": reason}, headers=auth_headers).status_code == 200
    s = SessionLocal()
    try:
        logs = s.query(OperationLog).filter(OperationLog.action == "撤销就诊状态").all()
        assert any(reason in (l.message or "") for l in logs)
        assert all(l.level == "WARN" for l in logs if l.action == "撤销就诊状态")
    finally:
        s.close()
