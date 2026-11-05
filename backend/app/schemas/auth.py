"""认证相关请求/响应模型"""
from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    department: str | None = None
    is_admin: bool
    role: str = "viewer"
    permissions: list[str] = []
    is_active: bool = True
    must_change_password: bool = True

    model_config = {"from_attributes": True}

    @classmethod
    def _split_permissions(cls, v):
        if isinstance(v, str):
            return [p for p in v.split(",") if p]
        return v or []

    _normalize = field_validator("permissions", mode="before")(_split_permissions)


class TokenOut(BaseModel):
    token: str
    user: UserOut
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserCreateRequest(BaseModel):
    username: str
    display_name: str | None = None
    department: str | None = None
    role: str = "viewer"
    password: str
    must_change_password: bool = True
    permissions: list[str] | None = None  # 显式权限集；为空则按 role 默认派生


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    department: str | None = None
    role: str | None = None
    permissions: list[str] | None = None  # 显式权限集；为空则不改动
    is_active: bool | None = None
    password: str | None = None
    reset_password: bool = False