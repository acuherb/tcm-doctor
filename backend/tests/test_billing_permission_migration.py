"""迁移 0022：存量账号补齐 billing 权限并显式化角色默认权限集（前后端权限一致）。"""
import uuid

from sqlalchemy import text

from app.database import engine
from app.migrations import m0022
from app.models.user import User


def _suffix():
    return uuid.uuid4().hex[:8]


def _mk_user(db, *, role, permissions, is_admin=False):
    s = _suffix()
    u = User(
        username=f"perm_test_{s}",
        password_hash="x",
        display_name="权限迁移测试",
        role=role,
        permissions=permissions,
        is_admin=is_admin,
    )
    db.add(u)
    db.commit()
    return u.id


def _perms(uid):
    with engine.connect() as conn:
        return conn.execute(text("SELECT permissions FROM users WHERE id = :id"), {"id": uid}).scalar()


def test_m0022_backfills_explicit_and_empty_perm_accounts(client, db_session):
    # 显式权限集（医生，不含 billing）
    explicit_id = _mk_user(db_session, role="doctor",
                           permissions="patient:read,prescription:write,stock:read")
    # 空权限集（走角色默认集，前端原本看不到 billing 入口）
    empty_id = _mk_user(db_session, role="pharmacist", permissions="")
    # 只读账号：不应获得 billing
    viewer_id = _mk_user(db_session, role="viewer", permissions="patient:read,stock:read")
    # 管理员：跳过（is_admin 绕过权限表）
    admin_id = _mk_user(db_session, role="admin", permissions="", is_admin=True)

    m0022()

    p = _perms(explicit_id)
    assert "billing:read" in p and "billing:write" in p
    # 原有权限保留
    assert "prescription:write" in p

    p2 = _perms(empty_id)
    assert "billing:read" in p2 and "billing:write" in p2
    # 角色默认集被显式化（药房含 stock:write）
    assert "stock:write" in p2

    assert "billing" not in (_perms(viewer_id) or "")
    assert "billing" not in (_perms(admin_id) or "")

    # 幂等：再跑一次不重复追加
    m0022()
    assert _perms(explicit_id).count("billing:write") == 1
