"""鉴权与权限测试（对应 P0 安全加固）"""
from app.database import SessionLocal
from app.models.user import User
from app.routers.auth import _hash_password


def _login(client, username, password):
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


def test_anonymous_read_requires_auth(client):
    # 只读接口必须登录后访问
    assert client.get("/api/v1/patients").status_code == 401


def test_guest_login_disabled(client):
    # 游客登录已默认关闭
    assert client.post("/api/v1/auth/guest").status_code == 403


def test_force_change_password_blocks_then_allows(client, db_session):
    user = User(
        username="chguser",
        password_hash=_hash_password("Chg12345"),
        display_name="改密测试",
        is_admin=False,
        must_change_password=True,
    )
    db_session.add(user)
    db_session.commit()

    tok = _login(client, "chguser", "Chg12345").json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    # 强制改密期间：读取业务接口被拦截
    assert client.get("/api/v1/patients", headers=h).status_code == 403

    # 改密后放行
    r = client.put(
        "/api/v1/auth/password",
        json={"old_password": "Chg12345", "new_password": "NewChg123"},
        headers=h,
    )
    assert r.status_code == 200
    tok2 = _login(client, "chguser", "NewChg123").json()["token"]
    h2 = {"Authorization": f"Bearer {tok2}"}
    assert client.get("/api/v1/patients", headers=h2).status_code == 200


def test_normal_user_read_allowed_write_forbidden(client, db_session):
    user = User(
        username="doc",
        password_hash=_hash_password("Doc12345"),
        display_name="医生",
        is_admin=False,
        must_change_password=False,
    )
    db_session.add(user)
    db_session.commit()

    tok = _login(client, "doc", "Doc12345").json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    # 普通用户可读
    assert client.get("/api/v1/patients", headers=h).status_code == 200
    # 普通用户不可写（写操作需管理员）
    assert (
        client.post("/api/v1/herbs", json={"name": "测试药材XYZ"}, headers=h).status_code
        == 403
    )
