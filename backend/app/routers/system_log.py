"""操作日志接口 — 列表 / 导出CSV / 清理(按保留天数)"""
import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.log import OperationLog
from app.models.user import User
from app.permissions import has_perm
from app.routers.auth import get_current_user

router = APIRouter(prefix="/system", tags=["系统"])


def _serialize(log: OperationLog) -> dict:
    return {
        "id": log.id, "created_at": log.created_at, "level": log.level,
        "user_id": log.user_id, "username": log.username, "action": log.action,
        "endpoint": log.endpoint, "method": log.method, "status_code": log.status_code,
        "success": log.success, "message": log.message, "target": log.target,
        "error_detail": log.error_detail,
        "ip": log.ip, "duration_ms": log.duration_ms,
    }


def _apply_filters(q, level, user_id, action, keyword, start, end, method=None):
    if level:
        # 支持逗号分隔多值（如 "WARN,ERROR"），便于前端「仅异常」tab 按级别后端过滤
        levels = [l.strip().upper() for l in level.split(",") if l.strip()]
        if levels:
            q = q.filter(OperationLog.level.in_(levels))
    if method:
        # 支持逗号分隔多值（如 "POST,PUT,PATCH,DELETE"），便于「关键操作」只看写请求
        methods = [m.strip().upper() for m in method.split(",") if m.strip()]
        if methods:
            q = q.filter(OperationLog.method.in_(methods))
    if user_id is not None:
        q = q.filter(OperationLog.user_id == user_id)
    if action:
        q = q.filter(OperationLog.action == action)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            func.coalesce(OperationLog.username, "").like(like)
            | func.coalesce(OperationLog.message, "").like(like)
            | func.coalesce(OperationLog.target, "").like(like)
            | func.coalesce(OperationLog.endpoint, "").like(like)
            | func.coalesce(OperationLog.action, "").like(like)
        )
    if start:
        q = q.filter(OperationLog.created_at >= start)
    if end:
        q = q.filter(OperationLog.created_at <= end + " 23:59:59.999999")
    return q


@router.get("/logs", summary="操作日志列表")
def list_logs(
    level: str | None = Query(None, description="INFO/WARN/ERROR，或逗号分隔多值如 WARN,ERROR"),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    keyword: str | None = Query(None),
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None),
    method: str | None = Query(None, description="GET/POST/...，或逗号分隔多值如 POST,PUT,DELETE"),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0, description="跳过前 N 条，用于「加载更多」分页"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not has_perm(current_user, "log:read"):
        raise HTTPException(status_code=403, detail="仅管理员可查看操作日志")
    q = _apply_filters(db.query(OperationLog), level, user_id, action, keyword, start, end, method)
    rows = q.order_by(OperationLog.id.desc()).offset(offset).limit(limit).all()
    return [_serialize(r) for r in rows]


@router.get("/logs/meta", summary="日志筛选项元数据(用户/动作下拉)")
def log_meta(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回筛选下拉候选值：操作人（取 id+用户名，管理员可直接选中）与出现过的动作名。

    前端据此把「用户ID 手输」「动作手输」换成下拉，避免管理员记 ID / 猜动作名。
    """
    if not has_perm(current_user, "log:read"):
        raise HTTPException(status_code=403, detail="仅管理员可查看操作日志")
    users = (
        db.query(OperationLog.user_id, OperationLog.username)
        .filter(OperationLog.user_id.isnot(None))
        .distinct()
        .all()
    )
    user_opts = sorted(
        [{"id": uid, "name": uname or f"#{uid}"} for uid, uname in users],
        key=lambda x: x["name"],
    )
    actions = (
        db.query(OperationLog.action)
        .filter(OperationLog.action.isnot(None), OperationLog.action != "")
        .distinct()
        .all()
    )
    action_opts = sorted({a[0] for a in actions if a[0]})
    return {"users": user_opts, "actions": action_opts}


@router.get("/logs/stats", summary="今日日志概览统计")
def log_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """今日概览：打开日志页即可看到「今天发生了多少、谁在用、有几条异常」。"""
    if not has_perm(current_user, "log:read"):
        raise HTTPException(status_code=403, detail="仅管理员可查看操作日志")
    day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    base = db.query(OperationLog).filter(OperationLog.created_at >= day_start)
    total = base.count()
    errors = base.filter(OperationLog.level.in_(["WARN", "ERROR"])).count()
    failed = base.filter(OperationLog.success == False).count()
    active_users = (
        base.filter(OperationLog.user_id.isnot(None))
        .with_entities(func.count(func.distinct(OperationLog.user_id)))
        .scalar()
    ) or 0
    return {
        "total": total,
        "abnormal": errors,
        "failed": failed,
        "active_users": active_users,
    }


@router.get("/logs/export", summary="导出操作日志CSV")
def export_logs(
    level: str | None = Query(None),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    keyword: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    method: str | None = Query(None, description="GET/POST/...，或逗号分隔多值如 POST,PUT,DELETE"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not has_perm(current_user, "log:read"):
        raise HTTPException(status_code=403, detail="仅管理员可导出操作日志")
    q = _apply_filters(db.query(OperationLog), level, user_id, action, keyword, start, end, method)
    rows = q.order_by(OperationLog.id.desc()).all()
    si = io.StringIO()
    si.write("﻿")  # UTF-8 BOM，保证 Excel 正确识别中文
    writer = csv.writer(si)
    # 导出不含 error_detail 堆栈：日志可能流传到诊所之外，堆栈会暴露服务器路径等内部信息
    writer.writerow(["时间", "级别", "用户ID", "用户名", "动作", "对象", "接口", "方法",
                     "状态码", "成功", "耗时(ms)", "消息", "IP"])
    for r in rows:
        writer.writerow([
            r.created_at, r.level, r.user_id or "", r.username or "",
            r.action or "", r.target or "", r.endpoint or "", r.method or "", r.status_code or "",
            "是" if r.success else "否", r.duration_ms if r.duration_ms is not None else "",
            r.message or "", r.ip or "",
        ])
    return Response(content=si.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=operation_logs.csv"})


@router.delete("/logs/clean", summary="清理操作日志(按保留天数, days=0 清空全部)")
def clean_logs(
    days: int = Query(90, ge=0, description="保留最近 N 天；0 表示清空全部"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not has_perm(current_user, "log:read"):
        raise HTTPException(status_code=403, detail="仅管理员可清理操作日志")
    q = db.query(OperationLog)
    if days and days > 0:
        cutoff = datetime.now() - timedelta(days=days)
        q = q.filter(OperationLog.created_at < cutoff)
    deleted = q.delete()
    db.commit()
    return {"deleted": deleted, "message": f"已清理 {deleted} 条（保留最近 {days} 天）" if days else f"已清空 {deleted} 条"}