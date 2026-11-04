"""认证路由 — 登录 / 登出 / 当前用户
使用标准库实现：hashlib.pbkdf2_hmac 密码哈希，secrets 令牌（存 DB 持久化）
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response

from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User, AuthToken
from app.schemas.auth import (
    LoginRequest,
    TokenOut,
    UserOut,
    ChangePasswordRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
from app.permissions import (
    ROLE_ADMIN, ROLE_LABELS, VALID_ROLES, has_perm,
    ROLE_DEFAULT_PERMSET, ALL_PERMISSIONS, PERMISSION_GROUPS,
)
from app.utils.operation_log import write_log

# 简单内存登录限流：同一 IP+用户名 在窗口内失败次数过多则拒绝
_LOGIN_MAX_FAILS = 5
_LOGIN_WINDOW_MIN = 5
_login_fails: dict[str, list] = {}

# 游客登录限流：同一 IP 1 分钟内最多 10 次，防止令牌被批量刷取（内存字典，多 worker 下为尽力而为）
_GUEST_MAX = 10
_guest_buckets: dict[str, list] = {}

router = APIRouter(prefix="/auth", tags=["认证"])

_ITER = 600_000          # 新密码哈希迭代次数（OWASP 2023 建议 ≥600k）
_LEGACY_ITER = 260_000    # 历史存量密码哈希的迭代次数（兼容升级前的数据）
_DIGEST = "sha256"
_TOKEN_TTL_DAYS = 30

AUTH_COOKIE_NAME = "tcm_session"
_TOKEN_MAX_AGE = _TOKEN_TTL_DAYS * 24 * 3600


def _extract_token(request: Request) -> str:
    """从 Authorization 头或 httpOnly 会话 Cookie 中取令牌（两者任一有效即可）。"""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(AUTH_COOKIE_NAME, "")


def _set_auth_cookie(response: Response, token: str, request: Request) -> None:
    """下发 httpOnly + SameSite=Lax 的会话 Cookie（HTTPS 时自动加 Secure）。"""
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=_TOKEN_MAX_AGE,
        secure=request.url.scheme == "https",
    )


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(_DIGEST, password.encode(), bytes.fromhex(salt), _ITER).hex()
    # 哈希中写入迭代次数，便于将来继续提升强度而不影响存量密码验证
    return f"{salt}${_ITER}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        parts = stored.split("$")
        if len(parts) == 3:
            salt, iter_str, digest = parts
            iters = int(iter_str)
        elif len(parts) == 2:
            # 升级前存量格式：salt$digest，按历史迭代次数验证，向后兼容
            salt, digest = parts
            iters = _LEGACY_ITER
        else:
            return False
        calc = hashlib.pbkdf2_hmac(_DIGEST, password.encode(), bytes.fromhex(salt), iters).hex()
        return secrets.compare_digest(calc, digest)
    except Exception:
        return False


def _issue_token(db: Session, user: User) -> AuthToken:
    token = AuthToken(
        token=secrets.token_hex(32),
        user_id=user.id,
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=_TOKEN_TTL_DAYS),
    )
    db.add(token)
    db.commit()
    return token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """依赖注入：校验 Authorization: Bearer <token> 或同名 httpOnly 会话 Cookie，返回当前用户"""
    token_str = _extract_token(request)
    if not token_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    record = (
        db.query(AuthToken)
        .filter(AuthToken.token == token_str)
        .first()
    )
    if not record or record.expires_at < datetime.now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员")
    return user


def _cleanup_login_fails() -> None:
    now = datetime.now()
    for key in list(_login_fails.keys()):
        _login_fails[key] = [
            t for t in _login_fails[key]
            if (now - t).total_seconds() < _LOGIN_WINDOW_MIN * 60
        ]
        if not _login_fails[key]:
            del _login_fails[key]


@router.post("/login", response_model=TokenOut, summary="用户登录")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    _cleanup_login_fails()
    fail_key = f"{client_ip}:{payload.username}"
    if len(_login_fails.get(fail_key, [])) >= _LOGIN_MAX_FAILS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请稍后再试",
        )

    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not _verify_password(payload.password, user.password_hash):
        _login_fails.setdefault(fail_key, []).append(datetime.now())
        write_log(level="WARN", username=payload.username, action="登录失败",
                  endpoint="/api/v1/auth/login", method="POST", status_code=401,
                  success=False, message="用户名或密码错误", ip=client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    _login_fails.pop(fail_key, None)
    if not getattr(user, "is_active", True):
        write_log(level="WARN", user_id=user.id, username=user.username, action="登录失败",
                  endpoint="/api/v1/auth/login", method="POST", status_code=403,
                  success=False, message="账号已停用", ip=client_ip)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员")
    token = _issue_token(db, user)
    write_log(level="INFO", user_id=user.id, username=user.username, action="登录",
              endpoint="/api/v1/auth/login", method="POST", status_code=200,
              success=True, message="登录成功", ip=client_ip)
    _set_auth_cookie(response, token.token, request)
    return TokenOut(
        token=token.token,
        user=UserOut.model_validate(user),
        must_change_password=user.must_change_password,
    )


@router.post("/guest", response_model=TokenOut, summary="游客一键登录（免密码）")
def guest_login(request: Request, response: Response, db: Session = Depends(get_db)):
    """生成游客令牌，无需密码；用于展示/试用。可随时切换账号登录。"""
    client_ip = request.client.host if request.client else "unknown"
    # 基础限流：同一 IP 1 分钟内最多 10 次
    now = datetime.now()
    bucket = _guest_buckets.setdefault(client_ip, [])
    bucket[:] = [t for t in bucket if (now - t).total_seconds() < 60]
    if len(bucket) >= _GUEST_MAX:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="操作过于频繁，请稍后再试")
    bucket.append(now)

    if not settings.allow_guest_login:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="游客登录已禁用")
    user = db.query(User).filter(User.username == "guest").first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="游客账号不存在")
    token = _issue_token(db, user)
    write_log(level="INFO", user_id=user.id, username=user.username, action="游客登录",
              endpoint="/api/v1/auth/guest", method="POST", status_code=200,
              success=True, message="游客一键登录", ip=client_ip)
    _set_auth_cookie(response, token.token, request)
    return TokenOut(token=token.token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="当前用户信息")
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.get("/permissions", summary="权限目录（权限点分组，供前端渲染权限表）")
def permission_catalog(current_user: User = Depends(get_current_user)):
    """返回权限点分组与角色默认集，前端据此渲染「权限表」勾选界面。需登录后方可获取，避免匿名泄露完整 RBAC 权限目录。"""
    return {"groups": PERMISSION_GROUPS, "role_defaults": ROLE_DEFAULT_PERMSET, "all": ALL_PERMISSIONS}


@router.post("/logout", summary="退出登录")
def logout(
    request: Request,
    response: Response = None,
    db: Session = Depends(get_db),
):
    uid = username = None
    ip = request.client.host if request else "unknown"
    token_str = _extract_token(request)
    if token_str:
        rec = db.query(AuthToken).filter(AuthToken.token == token_str).first()
        if rec:
            u = db.query(User).filter(User.id == rec.user_id).first()
            if u:
                uid, username = u.id, u.username
        db.query(AuthToken).filter(AuthToken.token == token_str).delete()
        db.commit()
    if response is not None:
        response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    write_log(level="INFO", user_id=uid, username=username, action="登出",
              endpoint="/api/v1/auth/logout", method="POST", status_code=200,
              success=True, message="退出登录", ip=ip)
    return {"message": "已退出登录"}


@router.put("/password", summary="修改密码（保留当前会话）")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码至少 6 位")
    current_user.password_hash = _hash_password(payload.new_password)
    current_user.must_change_password = False
    # 保留当前会话令牌（不踢下线）；其余令牌作废，避免密码泄露后被复用
    token_val = _extract_token(request)
    if token_val:
        db.query(AuthToken).filter(
            AuthToken.user_id == current_user.id, AuthToken.token != token_val
        ).delete()
    db.commit()
    return {"message": "密码已修改"}


def _require_perm(current_user: User, perm: str) -> None:
    if not has_perm(current_user, perm):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，无权执行该操作")


def _count_managers(db: Session, exclude_id: int | None = None) -> int:
    """可管理账号（is_admin 或拥有 user:write）且在启用的账号数。"""
    q = db.query(User).filter(User.is_active == True)
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return sum(1 for u in q.all() if u.is_admin or has_perm(u, "user:write"))


@router.get("/users", response_model=list[UserOut], summary="账号列表（需 user:read）")
def list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_perm(current_user, "user:read")
    users = db.query(User).filter(User.username != "guest").order_by(User.id).all()
    return [UserOut.model_validate(u) for u in users]


@router.post("/users", response_model=UserOut, summary="创建账号（需 user:write）")
def create_user(
    payload: UserCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_perm(current_user, "user:write")
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="角色非法")
    username = payload.username.strip()
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字符")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="初始密码至少 6 位")
    if username == "guest":
        raise HTTPException(status_code=400, detail="用户名 guest 为系统保留")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 显式权限优先；否则按所选角色模板派生默认权限集
    perms = payload.permissions if payload.permissions is not None else ROLE_DEFAULT_PERMSET.get(payload.role, [])
    user = User(
        username=username,
        display_name=(payload.display_name or "").strip() or None,
        password_hash=_hash_password(payload.password),
        role=payload.role,
        is_admin=(payload.role == ROLE_ADMIN),
        permissions=",".join(perms),
        is_active=True,
        must_change_password=payload.must_change_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_log(level="INFO", user_id=current_user.id, username=current_user.username, action="创建账号",
              endpoint="/api/v1/auth/users", method="POST", status_code=200,
              success=True, message=f"创建账号 {username}（{ROLE_LABELS.get(payload.role, payload.role)}）", ip="")
    return UserOut.model_validate(user)


@router.put("/users/{user_id}", response_model=UserOut, summary="修改账号角色/权限/状态（需 user:write）")
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_perm(current_user, "user:write")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")
    if user.username == "guest":
        raise HTTPException(status_code=400, detail="不能修改游客账号")

    revoke_tokens = False
    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="角色非法")
        # 防止把最后一个可管理账号降级
        if (user.is_admin or has_perm(user, "user:write")) and payload.role != ROLE_ADMIN and not (
            payload.permissions is not None and "user:write" in payload.permissions
        ) and _count_managers(db, exclude_id=user.id) == 0:
            raise HTTPException(status_code=400, detail="至少保留一名可管理账号")
        if payload.role != user.role:
            revoke_tokens = True
        user.role = payload.role
        user.is_admin = (payload.role == ROLE_ADMIN)
    if payload.permissions is not None:
        user.permissions = ",".join(payload.permissions)
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip() or None
    if payload.reset_password:
        # 改密码必须显式声明 reset_password=true，避免误提交 password 字段静默覆盖密码
        if not payload.password:
            raise HTTPException(status_code=400, detail="请填写新密码")
        if len(payload.password) < 6:
            raise HTTPException(status_code=400, detail="密码至少 6 位")
        user.password_hash = _hash_password(payload.password)
        user.must_change_password = True
        revoke_tokens = True
    if payload.is_active is not None:
        if user.id == current_user.id and not payload.is_active:
            raise HTTPException(status_code=400, detail="不能停用自己的账号")
        if (user.is_admin or has_perm(user, "user:write")) and not payload.is_active and _count_managers(db, exclude_id=user.id) == 0:
            raise HTTPException(status_code=400, detail="至少保留一名启用状态的可管理账号")
        if payload.is_active != user.is_active:
            revoke_tokens = True
        user.is_active = payload.is_active

    # 角色/密码/启用状态变动才使该用户已登录令牌失效；仅改显示名称不影响当前会话
    if revoke_tokens:
        db.query(AuthToken).filter(AuthToken.user_id == user.id).delete()
    db.commit()
    db.refresh(user)
    write_log(level="INFO", user_id=current_user.id, username=current_user.username, action="修改账号",
              endpoint=f"/api/v1/auth/users/{user_id}", method="PUT", status_code=200,
              success=True, message=f"修改账号 {user.username}", ip="")
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}", summary="删除账号（需 user:write）")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_perm(current_user, "user:write")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    if user.username == "guest":
        raise HTTPException(status_code=400, detail="不能删除游客账号")
    if (user.is_admin or has_perm(user, "user:write")) and _count_managers(db, exclude_id=user.id) == 0:
        raise HTTPException(status_code=400, detail="至少保留一名可管理账号")

    db.query(AuthToken).filter(AuthToken.user_id == user.id).delete()
    # 解除该用户作为开方医师的处方关联（doctor_id 置空），避免外键约束下删除失败
    from app.models.prescription import Prescription
    db.query(Prescription).filter(Prescription.doctor_id == user.id).update(
        {Prescription.doctor_id: None}
    )
    username = user.username
    db.delete(user)
    db.commit()
    write_log(level="INFO", user_id=current_user.id, username=current_user.username, action="删除账号",
              endpoint=f"/api/v1/auth/users/{user_id}", method="DELETE", status_code=200,
              success=True, message=f"删除账号 {username}", ip="")
    return {"message": "账号已删除"}