"""权限模型 — 以「权限点」为中心的灵活权限表

单一事实来源：网关中间件（main.py）与账号管理接口（routers/auth.py）共用。

设计：
- 每个账号拥有若干「权限点」（如 patient:read / stock:write），存于 User.permissions（逗号分隔文本）。
- 管理员(is_admin) 视为拥有全部权限（超级用户，绕过权限表）。
- DOMAIN_PERMS 把 API 路由域映射到「读权限点 / 写权限点」，中间件据此放行；
  写权限点为 None 表示该域只读，读权限点为 "*" 表示所有已登录用户可读（如诊所配置、统计）。
- 创建账号时可用「角色模板」一键预填权限，也可在权限表里逐项勾选，自由组合 —— 不再写死四类人。
"""

ROLE_ADMIN = "admin"
ROLE_DOCTOR = "doctor"
ROLE_PHARMACIST = "pharmacist"
ROLE_VIEWER = "viewer"
ROLE_CUSTOM = "custom"

VALID_ROLES = (ROLE_ADMIN, ROLE_DOCTOR, ROLE_PHARMACIST, ROLE_VIEWER, ROLE_CUSTOM)

ROLE_LABELS = {
    ROLE_ADMIN: "管理员",
    ROLE_DOCTOR: "医生",
    ROLE_PHARMACIST: "药房",
    ROLE_VIEWER: "只读",
    ROLE_CUSTOM: "自定义",
}

# ── 权限点目录（前端按此渲染勾选表）──
PERMISSION_GROUPS = [
    {"group": "患者与诊疗", "perms": [
        {"key": "patient:read", "label": "查看患者 / 就诊 / 随访"},
        {"key": "patient:write", "label": "新建 / 编辑患者与就诊"},
    ]},
    {"group": "处方与问诊", "perms": [
        {"key": "prescription:read", "label": "查看处方 / 方库 / 问诊记录"},
        {"key": "prescription:write", "label": "开具 / 编辑处方"},
    ]},
    {"group": "库存", "perms": [
        {"key": "stock:read", "label": "查看库存 / 流水 / 报表"},
        {"key": "stock:write", "label": "入库 / 出库 / 盘点 / 供应商"},
    ]},
    {"group": "基础资料", "perms": [
        {"key": "dict:read", "label": "查看药材 / 穴位 / 字典 / 文库"},
        {"key": "dict:write", "label": "维护药材 / 穴位 / 字典 / 文库"},
    ]},
    {"group": "统计", "perms": [
        {"key": "stats:read", "label": "查看统计报表"},
    ]},
    {"group": "收费", "perms": [
        {"key": "billing:read", "label": "查看收费单 / 收据"},
        {"key": "billing:write", "label": "开具收费 / 收款 / 退费"},
    ]},
    {"group": "用户与系统", "perms": [
        {"key": "user:read", "label": "查看账号"},
        {"key": "user:write", "label": "创建 / 管理账号与权限"},
        {"key": "log:read", "label": "查看操作日志"},
        {"key": "system:read", "label": "查看系统设置 / 备份"},
        {"key": "system:write", "label": "修改设置 / 备份恢复"},
    ]},
]

ALL_PERMISSIONS = sorted({p["key"] for g in PERMISSION_GROUPS for p in g["perms"]})

# 角色 → 默认权限集（创建账号选「角色模板」时预填；可在此基础上增删）
ROLE_DEFAULT_PERMSET = {
    ROLE_ADMIN: list(ALL_PERMISSIONS),
    ROLE_DOCTOR: ["patient:read", "patient:write", "prescription:read", "prescription:write",
                  "stock:read", "stock:write", "stats:read", "dict:read", "billing:read", "billing:write"],
    ROLE_PHARMACIST: ["patient:read", "stock:read", "stock:write", "dict:read", "stats:read", "billing:read", "billing:write"],
    ROLE_VIEWER: ["patient:read", "prescription:read", "stock:read", "dict:read", "stats:read"],
    ROLE_CUSTOM: [],
}

# 路由域前缀（不含 /api/v1）→ (读权限点, 写权限点)
#   读权限点 "*"  = 所有已登录用户可读（如诊所配置、统计）；
#   写权限点 None = 该域只读。
DOMAIN_PERMS: dict[str, tuple[str, str | None]] = {
    "/patients": ("patient:read", "patient:write"),
    "/herbs": ("dict:read", "dict:write"),
    "/stock": ("stock:read", "stock:write"),
    "/prescriptions": ("prescription:read", "prescription:write"),
    "/diagnosis": ("prescription:read", "prescription:write"),
    "/acupoints": ("dict:read", "dict:write"),
    "/acupoint-formulas": ("dict:read", "dict:write"),
    "/knowledge": ("dict:read", "dict:write"),
    "/dictionaries": ("dict:read", "dict:write"),
    "/followup-reminders": ("patient:read", "patient:write"),
    "/stats": ("*", "stats:read"),
    "/backup": ("system:read", "system:write"),
    # 操作日志域：查看需 log:read（比通用 system:read 更细粒度，与权限目录/路由守卫一致）；
    # 清理(DELETE)需 system:write。最长前缀匹配优先于 /system，避免被通用域覆盖。
    "/system/logs": ("log:read", "system:write"),
    "/system": ("system:read", "system:write"),
    "/config": ("*", "system:write"),
    # 模板/基础数据包：清单与导出对所有登录账号可读，导入（写内容库）要求 system:write。
    # 此前未登记导致按 fail-closed 全量 403，模板工具栏与一键安装都不可用。
    "/templates": ("*", "system:write"),
    "/billing": ("billing:read", "billing:write"),
}

# 账号管理接口单独映射（中间件整体跳过 /auth，故在 auth 路由内自行校验 user:write）
AUTH_USERS_PREFIX = "/api/v1/auth/users"

_API_PREFIX = "/api/v1"

# 方库属基础资料，仅维护者可写（医生可预览开方）；写操作要求 dict:write
_FORMULA_WRITE_PREFIXES = ("/prescriptions/classic-formulas", "/acupoint-formulas")


def _strip_api_prefix(path: str) -> str:
    return path[len(_API_PREFIX):] if path.startswith(_API_PREFIX) else path


def resolve_domain(path: str) -> str | None:
    """按最长前缀匹配业务域；未登记的路径返回 None。"""
    rel = _strip_api_prefix(path)
    best = None
    for prefix in DOMAIN_PERMS:
        if rel == prefix or rel.startswith(prefix + "/"):
            if best is None or len(prefix) > len(best):
                best = prefix
    return best


def user_permissions(user) -> set[str]:
    """返回账号拥有的权限点集合。

    - 管理员(is_admin) 拥有全部权限（超级用户）；
    - 显式配置权限(permissions 非空) 直接使用；
    - 未配置时回退到角色默认集（兼容老库 / 直建账号，保证升级后不被突然锁死）。
    """
    if getattr(user, "is_admin", False):
        return set(ALL_PERMISSIONS)
    raw = getattr(user, "permissions", None) or ""
    if raw:
        return {p for p in raw.split(",") if p}
    role = getattr(user, "role", None)
    return set(ROLE_DEFAULT_PERMSET.get(role, []))


def has_perm(user, perm: str) -> bool:
    return perm in user_permissions(user)


def is_formula_library_write(path: str) -> bool:
    """是否为方库维护类写的请求（导入/导出/新增/编辑/删除）。"""
    rel = _strip_api_prefix(path)
    return any(rel == p or rel.startswith(p + "/") for p in _FORMULA_WRITE_PREFIXES)


def has_read(path: str, user) -> bool:
    """该账号能否读取该路径（user 为 User 对象）。"""
    if user is None:
        return False
    domain = resolve_domain(path)
    if domain is None:
        # 未登记路径默认拒绝（fail-closed），与 has_write 一致；
        # 新增只读接口须显式登记到 DOMAIN_PERMS，避免漏登记即对所有登录用户开放。
        return False
    read_perm, _ = DOMAIN_PERMS[domain]
    if read_perm == "*":
        return True
    return has_perm(user, read_perm)


def has_write(path: str, user) -> bool:
    """该账号能否写该路径。"""
    if user is None:
        return False
    domain = resolve_domain(path)
    if domain is None:
        # 未登记路径默认拒绝写入（安全默认）
        return False
    if is_formula_library_write(path):
        return has_perm(user, "dict:write")
    _, write_perm = DOMAIN_PERMS[domain]
    if not write_perm:
        return False
    return has_perm(user, write_perm)
