"""用户与认证令牌模型"""
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="所属科室（挂号台科室下拉由启用账号去重派生）"
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="超级管理员：拥有全部权限，绕过权限表")
    role: Mapped[str] = mapped_column(String(20), default="viewer", nullable=False, comment="角色模板/显示标签: admin/doctor/pharmacist/viewer/custom")
    permissions: Mapped[str] = mapped_column(Text, default="", nullable=False, comment="权限点清单(逗号分隔)，为空时回退到角色默认集")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="账号是否启用，停用后拒绝登录")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class AuthToken(Base):
    """登录令牌 — 存持久化，重启服务不掉线"""
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship("User")