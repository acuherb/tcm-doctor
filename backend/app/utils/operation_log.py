"""操作日志写入工具 — 供中间件与显式审计(登录/登出/关键业务)调用"""
from datetime import datetime

from app.database import SessionLocal
from app.models.log import OperationLog


def write_log(
    level: str = "INFO",
    user_id: int | None = None,
    username: str | None = None,
    action: str | None = None,
    endpoint: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
    success: bool = True,
    message: str | None = None,
    error_detail: str | None = None,
    ip: str | None = None,
    duration_ms: float | None = None,
) -> None:
    """写入一条操作日志；独立会话，写库失败不影响主流程。"""
    db = SessionLocal()
    try:
        db.add(OperationLog(
            level=level, user_id=user_id, username=username, action=action,
            endpoint=endpoint, method=method, status_code=status_code, success=success,
            message=message, error_detail=error_detail, ip=ip, duration_ms=duration_ms,
            created_at=datetime.now(),
        ))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def log_action(level: str, action: str, *, user_id=None, username=None, success=True,
               message=None, error_detail=None, ip=None):
    """语义化快捷方法：仅关心动作/用户/成败/消息。"""
    write_log(level=level, user_id=user_id, username=username, action=action,
              success=success, message=message, error_detail=error_detail, ip=ip)
