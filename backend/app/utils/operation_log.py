"""操作日志写入工具 — 供中间件与显式审计(登录/登出/关键业务)调用"""
import re
from datetime import datetime

from app.database import SessionLocal
from app.models.log import OperationLog

# 入库前对敏感信息打码，避免手机号 / 身份证号落库
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_IDCARD_RE = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")


def _mask_sensitive(text: str | None) -> str | None:
    if not text:
        return text
    # 422 校验错误的 detail 是 list（非 str），此处必须容错，否则后台审计任务抛 TypeError、日志整条丢失
    if not isinstance(text, str):
        text = str(text)
    text = _PHONE_RE.sub(lambda m: m.group(1)[:3] + "****" + m.group(1)[-4:], text)
    text = _IDCARD_RE.sub(lambda m: m.group(1)[:6] + "********" + m.group(1)[-4:], text)
    return text


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
    target: str | None = None,
) -> None:
    """写入一条操作日志；独立会话，写库失败不影响主流程。"""
    # 脱敏 + 截断：message 限 500 字（与列长一致）；error_detail 仅 5xx 场景传入，截到 4000 防日志表膨胀
    if message:
        message = _mask_sensitive(message)[:500]
    if error_detail:
        error_detail = _mask_sensitive(error_detail)[:4000]
    if target:
        target = _mask_sensitive(target)[:300]
    if action:
        action = action[:100]
    db = SessionLocal()
    try:
        db.add(OperationLog(
            level=level, user_id=user_id, username=username, action=action,
            endpoint=endpoint, method=method, status_code=status_code, success=success,
            message=message, target=target, error_detail=error_detail, ip=ip, duration_ms=duration_ms,
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

def set_log_context(request, *, action: str | None = None, message: str | None = None,
                    target: str | None = None, level: str | None = None) -> None:
    """业务路由补充审计上下文，交给操作日志中间件统一落库。

    显式 write_log 会与中间件自动采集产生两条重复日志，且缺少状态码/耗时/IP。
    路由只需声明「做了什么、对谁、为什么」，其余元数据由中间件补齐。
    """
    if action is not None:
        request.state.log_action = action
    if message is not None:
        request.state.log_message = message
    if target is not None:
        request.state.log_target = target
    if level is not None:
        request.state.log_level = level
