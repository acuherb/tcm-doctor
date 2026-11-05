"""挂号台「科室 / 接诊医师」与账号管理联动的回归测试。

科室不另建字典，由启用医生/管理员账号的 department 去重派生；
挂号时 doctor_id 必须指向有效账号，并落库到 Visit.doctor_id（此前是死字段）。
"""
import uuid

from app.models.user import User
from app.routers.auth import _hash_password


def _suffix():
    return uuid.uuid4().hex[:8]


def _make_user(db_session, *, role="doctor", active=True, department="中医内科", name=None):
    s = _suffix()
    u = User(
        username=f"acct_{s}",
        password_hash=_hash_password("Pass123"),
        display_name=name or f"医师{s[:4]}",
        role=role,
        department=department,
        is_active=active,
        must_change_password=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


# ── 账号管理维护科室 ──

def test_user_crud_persists_department(client, db_session, auth_headers):
    s = _suffix()
    created = client.post("/api/v1/auth/users", json={
        "username": f"newdoc_{s}", "password": "Pass123", "role": "doctor",
        "display_name": "李医师", "department": "针灸科",
    }, headers=auth_headers)
    assert created.status_code == 200, created.text
    assert created.json()["department"] == "针灸科"
    uid = created.json()["id"]

    updated = client.put(f"/api/v1/auth/users/{uid}", json={"department": "推拿科"}, headers=auth_headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["department"] == "推拿科"

    listed = client.get("/api/v1/auth/users", headers=auth_headers).json()
    assert next(u for u in listed if u["id"] == uid)["department"] == "推拿科"


# ── /registration/options ──

def test_options_come_from_active_doctor_accounts(client, db_session, auth_headers):
    doc = _make_user(db_session, department="中医内科", name="张医师")
    _make_user(db_session, role="viewer", department="不该出现的科室", name="只读员")
    _make_user(db_session, active=False, department="停用人科室", name="停用医师")
    _make_user(db_session, role="pharmacist", department="药房", name="药师")

    r = client.get("/api/v1/registration/options", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "中医内科" in body["departments"]
    assert "不该出现的科室" not in body["departments"]
    assert "停用人科室" not in body["departments"]
    assert "药房" not in body["departments"]
    assert any(d["id"] == doc.id and d["name"] == "张医师" for d in body["doctors"])
    assert all(d["name"] not in ("只读员", "停用医师", "药师") for d in body["doctors"])


def test_options_do_not_require_user_read_permission(client, db_session, auth_headers):
    """挂号员通常没有 user:read，仍能拿到科室/医师选项（只暴露必要字段）。"""
    s = _suffix()
    viewer = client.post("/api/v1/auth/users", json={
        "username": f"viewer_{s}", "password": "Pass123", "role": "viewer",
        "must_change_password": False,  # 否则登录后被「请先修改初始密码」中间件拦截
    }, headers=auth_headers)
    assert viewer.status_code == 200
    login = client.post("/api/v1/auth/login",
                        json={"username": f"viewer_{s}", "password": "Pass123"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    assert client.get("/api/v1/auth/users", headers=headers).status_code == 403
    r = client.get("/api/v1/registration/options", headers=headers)
    assert r.status_code == 200, r.text
    assert "departments" in r.json() and "doctors" in r.json()
    assert all(set(d) == {"id", "name", "department"} for d in r.json()["doctors"])


# ── 挂号落库 ──

def test_register_with_doctor_persists_doctor_id(client, db_session, auth_headers):
    doc = _make_user(db_session, department="中医内科", name="王医师")
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"挂号联动_{_suffix()}"},
        "doctor_id": doc.id,
        "department": "随意乱填的科室",  # 选了医师应以其账号科室为准
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    v = r.json()["visit"]
    assert v["doctor_id"] == doc.id
    assert v["doctor_name"] == "王医师"
    assert v["department"] == "中医内科"

    detail = client.get(f"/api/v1/registration/{v['id']}", headers=auth_headers)
    assert detail.json()["doctor_name"] == "王医师"
    items = client.get("/api/v1/registration/queue", headers=auth_headers).json()["items"]
    assert next(i for i in items if i["id"] == v["id"])["doctor_name"] == "王医师"


def test_register_rejects_invalid_doctor(client, db_session, auth_headers):
    inactive = _make_user(db_session, active=False, name="停用医师")
    viewer = _make_user(db_session, role="viewer", name="只读员")
    for did in (999999, inactive.id, viewer.id):
        r = client.post("/api/v1/registration", json={
            "new_patient": {"name": f"无效医师_{_suffix()}"},
            "doctor_id": did,
        }, headers=auth_headers)
        assert r.status_code == 400, r.text
        assert "接诊医师" in r.json()["detail"]


def test_register_department_only_still_works(client, db_session, auth_headers):
    """只分诊到科室、暂不指定医师，历史路径保持可用。"""
    r = client.post("/api/v1/registration", json={
        "new_patient": {"name": f"仅科室_{_suffix()}"},
        "department": "中医内科",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["visit"]["department"] == "中医内科"
    assert r.json()["visit"]["doctor_id"] is None
    assert r.json()["visit"]["doctor_name"] is None
