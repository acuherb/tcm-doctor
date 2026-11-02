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
from app.routers.auth import get_current_user

router = APIRouter(prefix="/system", tags=["系统"])


def _serialize(log: OperationLog) -> dict:
    return {
        "id": log.id, "created_at": log.created_at, "level": log.level,
        "user_id": log.user_id, "username": log.username, "action": log.action,
        "endpoint": log.endpoint, "method": log.method, "status_code": log.status_code,
        "success": log.success, "message": log.message, "error_detail": log.error_detail,
        "ip": log.ip, "duration_ms": log.duration_ms,
    }


def _apply_filters(q, level, user_id, action, keyword, start, end):
    if level:
        # 支持逗号分隔多值（如 "WARN,ERROR"），便于前端「仅异常」tab 按级别后端过滤
        levels = [l.strip().upper() for l in level.split(",") if l.strip()]
        if levels:
            q = q.filter(OperationLog.level.in_(levels))
    if user_id is not None:
        q = q.filter(OperationLog.user_id == user_id)
    if action:
        q = q.filter(OperationLog.action == action)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            func.coalesce(OperationLog.username, "").like(like)
            | func.coalesce(OperationLog.message, "").like(like)
            | func.coalesce(OperationLog.endpoint, "").like(like)
            | func.coalesce(OperationLog.action, "").like(like)
        )
    if start:
        q = q.filter(OperationLog.created_at >= start)
    if end:
        q = q.filter(OperationLog.created_at <= end + " 23:59:59")
    return q


@router.get("/logs", summary="操作日志列表")
def list_logs(
    level: str | None = Query(None, description="INFO/WARN/ERROR，或逗号分隔多值如 WARN,ERROR"),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    keyword: str | None = Query(None),
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可查看操作日志")
    q = _apply_filters(db.query(OperationLog), level, user_id, action, keyword, start, end)
    rows = q.order_by(OperationLog.id.desc()).limit(limit).all()
    return [_serialize(r) for r in rows]


@router.get("/logs/export", summary="导出操作日志CSV")
def export_logs(
    level: str | None = Query(None),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    keyword: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可导出操作日志")
    q = _apply_filters(db.query(OperationLog), level, user_id, action, keyword, start, end)
    rows = q.order_by(OperationLog.id.desc()).all()
    si = io.StringIO()
    si.write("﻿")  # UTF-8 BOM，保证 Excel 正确识别中文
    writer = csv.writer(si)
    writer.writerow(["时间", "级别", "用户ID", "用户名", "动作", "接口", "方法",
                     "状态码", "成功", "耗时(ms)", "消息", "明细", "IP"])
    for r in rows:
        writer.writerow([
            r.created_at, r.level, r.user_id or "", r.username or "",
            r.action or "", r.endpoint or "", r.method or "", r.status_code or "",
            "是" if r.success else "否", r.duration_ms if r.duration_ms is not None else "",
            r.message or "", (r.error_detail or "").replace("\n", " ")[:2000], r.ip or "",
        ])
    return Response(content=si.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=operation_logs.csv"})


@router.delete("/logs/clean", summary="清理操作日志(按保留天数, days=0 清空全部)")
def clean_logs(
    days: int = Query(90, ge=0, description="保留最近 N 天；0 表示清空全部"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可清理操作日志")
    q = db.query(OperationLog)
    if days and days > 0:
        cutoff = datetime.now() - timedelta(days=days)
        q = q.filter(OperationLog.created_at < cutoff)
    deleted = q.delete()
    db.commit()
    return {"deleted": deleted, "message": f"已清理 {deleted} 条（保留最近 {days} 天）" if days else f"已清空 {deleted} 条"}
