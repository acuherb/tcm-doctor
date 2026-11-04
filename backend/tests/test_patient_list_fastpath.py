"""患者列表搜索分页快路径测试：验证 SQL 真分页与原全量聚合路径语义一致。

list_patients 有两路径：
- 快路径（默认/仅搜索/体质/过敏筛选）：SQL count + offset/limit，只给当前页补派生字段；
- 全量路径（tag / improvement / sort_by=last_visit_date）：先聚合全部患者再 Python 筛选排序。
本测试确保两条路径返回的 total、分页结果与派生字段一致。
"""
import uuid

from app.models.patient import Patient
from app.models.visit import Visit
from app.models.followup import FollowUp


def _seed(db_session):
    s = uuid.uuid4().hex[:8]
    p1 = Patient(name=f"甲_{s}", phone="13800000001", tags=["老患者"])
    p2 = Patient(name=f"乙_{s}", phone="13800000002", tags=[])
    p3 = Patient(name=f"丙_{s}", phone="13800000003", tags=["老患者"])
    db_session.add_all([p1, p2, p3])
    db_session.commit()

    db_session.add(Visit(patient_id=p1.id, visit_date="2026-01-01", chief_complaint="x"))
    db_session.add(Visit(patient_id=p2.id, visit_date="2026-02-01", chief_complaint="x"))
    db_session.commit()
    db_session.add(FollowUp(patient_id=p1.id, followup_date="2026-01-10", improvement="好转"))
    db_session.add(FollowUp(patient_id=p2.id, followup_date="2026-02-10", improvement="反复"))
    db_session.commit()
    return s, [p1.id, p2.id, p3.id]


def test_fastpath_paging_and_derived_fields(client, db_session, auth_headers):
    s, ids = _seed(db_session)

    # 快路径：按唯一后缀搜索限定范围，total 应为 3，且派生字段齐备
    r = client.get("/api/v1/patients", params={"search": s, "page_size": 100}, headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 3
    assert {it["id"] for it in data["items"]} == set(ids)
    by_id = {it["id"]: it for it in data["items"]}
    assert by_id[ids[0]]["last_visit_date"] == "2026-01-01"
    assert by_id[ids[0]]["active_status"] == "在治"       # 最近改善「好转」
    assert by_id[ids[1]]["active_status"] == "停诊"       # 最近改善「反复」
    assert by_id[ids[2]]["active_status"] == "新诊"       # 无就诊记录

    # 真分页：page=2 & page_size=1 应返回同一排序下的第 2 条
    full_order = [it["id"] for it in data["items"]]
    r2 = client.get(
        "/api/v1/patients", params={"search": s, "page": 2, "page_size": 1}, headers=auth_headers,
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["total"] == 3
    assert len(d2["items"]) == 1
    assert d2["items"][0]["id"] == full_order[1]


def test_full_agg_path_and_fastpath_cover_same_patients(client, db_session, auth_headers):
    s, ids = _seed(db_session)

    # 全量路径：按最近就诊排序（触发 needs_full_agg）
    r_sort = client.get(
        "/api/v1/patients",
        params={"search": s, "page_size": 100, "sort_by": "last_visit_date"},
        headers=auth_headers,
    )
    assert r_sort.status_code == 200
    d_sort = r_sort.json()
    assert d_sort["total"] == 3
    assert d_sort["items"][0]["id"] == ids[1]      # p2 就诊 2026-02-01 最新

    # 全量路径：标签 / 改善筛选（依赖聚合）
    r_tag = client.get("/api/v1/patients", params={"search": s, "tag": "老患者", "page_size": 100}, headers=auth_headers)
    assert {it["id"] for it in r_tag.json()["items"]} == {ids[0], ids[2]}
    r_imp = client.get("/api/v1/patients", params={"search": s, "improvement": "好转", "page_size": 100}, headers=auth_headers)
    assert {it["id"] for it in r_imp.json()["items"]} == {ids[0]}

    # 快路径与全量路径覆盖同一批患者（只是排序不同）
    r_fast = client.get("/api/v1/patients", params={"search": s, "page_size": 100}, headers=auth_headers)
    assert {it["id"] for it in r_fast.json()["items"]} == {it["id"] for it in d_sort["items"]}


def test_archived_patient_excluded_from_fastpath(client, db_session, auth_headers):
    from datetime import datetime
    s, ids = _seed(db_session)
    db_session.get(Patient, ids[2]).deleted_at = datetime.now()
    db_session.commit()

    r = client.get("/api/v1/patients", params={"search": s, "page_size": 100}, headers=auth_headers)
    assert r.json()["total"] == 2
    assert ids[2] not in {it["id"] for it in r.json()["items"]}

    # include_deleted 仍可找回，语义不变
    r2 = client.get(
        "/api/v1/patients", params={"search": s, "page_size": 100, "include_deleted": True}, headers=auth_headers,
    )
    assert r2.json()["total"] == 3
