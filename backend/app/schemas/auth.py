"""认证相关请求/响应模型"""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    is_admin: bool

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    token: str
    user: UserOut
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str