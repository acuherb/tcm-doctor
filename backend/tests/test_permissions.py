"""权限矩阵单测（has_read / has_write / resolve_domain）

覆盖此前修复的关键约定：
- 未登记域默认拒绝（fail-closed），与 has_write 一致；
- 通配符 "*" 域所有已登录用户可读；
- 角色默认权限集按 DOMAIN_PERMS 正确放行/拦截。
"""
from app.permissions import has_read, has_write, resolve_domain


class _User:
    def __init__(self, is_admin=False, permissions=None, role=None):
        self.is_admin = is_admin
        self.permissions = permissions
        self.role = role


def _admin():
    return _User(is_admin=True)


def _role(role):
    # 不显式给 permissions，回退到角色默认集
    return _User(role=role)


def test_unregistered_domain_fail_closed():
    # 未登记域：读/写均默认拒绝（fail-closed），且不依赖角色
    assert resolve_domain("/api/v1/totally/new/domain") is None
    assert has_read("/api/v1/totally/new/domain", _role("viewer")) is False
    assert has_write("/api/v1/totally/new/domain", _role("viewer")) is False
    # 即便是管理员，未登记域也按 fail-closed 拒绝（未登记路径不应存在）
    assert has_read("/api/v1/totally/new/domain", _admin()) is False


def test_admin_full_access_on_registered_domains():
    a = _admin()
    assert has_read("/api/v1/patients", a) is True
    assert has_write("/api/v1/patients", a) is True
    assert has_read("/api/v1/herbs", a) is True
    assert has_write("/api/v1/herbs", a) is True


def test_config_wildcard_read_open_to_all_logged_in():
    # config 读权限点为 "*"：任何已登录用户可读
    assert has_read("/api/v1/config", _role("viewer")) is True
    # 但写仍受 system:write 约束：viewer 无该权限
    assert has_write("/api/v1/config", _role("viewer")) is False


def test_doctor_role_default_permissions():
    d = _role("doctor")
    # 医生可读写患者、库存（在默认集内）
    assert has_read("/api/v1/patients", d) is True
    assert has_write("/api/v1/patients", d) is True
    assert has_read("/api/v1/stock/items", d) is True
    assert has_write("/api/v1/stock/items", d) is True
    # 医生不可维护基础资料（dict:write 不在医生默认集）
    assert has_write("/api/v1/herbs", d) is False


def test_viewer_role_write_denied():
    v = _role("viewer")
    assert has_read("/api/v1/patients", v) is True
    assert has_write("/api/v1/patients", v) is False
    # 只读账号不可写库存
    assert has_write("/api/v1/stock/items", v) is False


def test_system_logs_requires_log_read():
    v = _role("viewer")
    # 操作日志域读需 log:read（比通用 system:read 更细），viewer 无 -> 拒绝
    assert has_read("/api/v1/system/logs", v) is False
    assert has_write("/api/v1/system/logs", v) is False
    # 管理员放行
    assert has_read("/api/v1/system/logs", _admin()) is True
