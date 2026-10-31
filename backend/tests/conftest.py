"""pytest 公共 fixture：固定使用临时数据库，避免污染开发库。"""
import os
import tempfile

# 必须在导入 app 之前固定测试数据库
_tmp = tempfile.mkdtemp(prefix="tcm_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ALLOW_GUEST_LOGIN"] = "false"
os.environ["ENABLE_SEMANTIC_SEARCH"] = "false"

import pytest
from fastapi.testclient import TestClient
from app.database import SessionLocal
from app.models.user import User
from app.routers.auth import _hash_password


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def admin_token(client, db_session):
    """保证存在一个已知口令的管理员，避免受默认 admin 密码状态影响"""
    user = db_session.query(User).filter(User.username == "testadmin").first()
    if not user:
        user = User(
            username="testadmin",
            password_hash=_hash_password("TestAdm1n"),
            display_name="测试管理员",
            is_admin=True,
            must_change_password=False,
        )
        db_session.add(user)
        db_session.commit()
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "testadmin", "password": "TestAdm1n"},
    )
    return r.json()["token"]


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
