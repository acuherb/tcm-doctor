"""认证路由 — 登录 / 登出 / 当前用户
使用标准库实现：hashlib.pbkdf2_hmac 密码哈希，secrets 令牌（存 DB 持久化）
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User, AuthToken
from app.schemas.auth import LoginRequest, TokenOut, UserOut, ChangePasswordRequest

# 简单内存登录限流：同一 IP+用户名 在窗口内失败次数过多则拒绝
_LOGIN_MAX_FAILS = 5
_LOGIN_WINDOW_MIN = 5
_login_fails: dict[str, list] = {}

# 游客登录限流：同一 IP 1 分钟内最多 10 次，防止令牌被批量刷取（内存字典，多 worker 下为尽力而为）
_GUEST_MAX = 10
_guest_buckets: dict[str, list] = {}

router = APIRouter(prefix="/auth", tags=["认证"])

_ITER = 260_000
_DIGEST = "sha256"
_TOKEN_TTL_DAYS = 30

_bearer = HTTPBearer(auto_error=False)


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(_DIGEST, password.encode(), bytes.fromhex(salt), _ITER).hex()
    return f"{salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac(_DIGEST, password.encode(), bytes.fromhex(salt), _ITER).hex()
    return secrets.compare_digest(calc, digest)


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
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """依赖注入：校验 Authorization: Bearer <token>，返回当前用户"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    record = (
        db.query(AuthToken)
        .filter(AuthToken.token == credentials.credentials)
        .first()
    )
    if not record or record.expires_at < datetime.now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
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
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    _login_fails.pop(fail_key, None)
    token = _issue_token(db, user)
    return TokenOut(
        token=token.token,
        user=UserOut.model_validate(user),
        must_change_password=user.must_change_password,
    )


@router.post("/guest", response_model=TokenOut, summary="游客一键登录（免密码）")
def guest_login(request: Request, db: Session = Depends(get_db)):
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
    return TokenOut(token=token.token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="当前用户信息")
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.post("/logout", summary="退出登录")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    if credentials is not None:
        db.query(AuthToken).filter(AuthToken.token == credentials.credentials).delete()
        db.commit()
    return {"message": "已退出登录"}


@router.put("/password", summary="修改密码")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码至少 6 位")
    current_user.password_hash = _hash_password(payload.new_password)
    current_user.must_change_password = False
    # 改密后使该用户所有其它令牌失效
    db.query(AuthToken).filter(AuthToken.user_id == current_user.id).delete()
    db.commit()
    return {"message": "密码已修改"}