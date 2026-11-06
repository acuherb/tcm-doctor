"""AI 用量与成本统计路由。

读需 ai_usage:read（仅管理员/获授权账号），清空记录需 system:write。
费用为按当前配置单价的估算值，最终以服务商账单为准。
"""
import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.ai_usage import AiUsageLog
from app.permissions import has_perm
from app.routers.auth import get_current_user
from app.services.ai_usage import pricing_configured

router = APIRouter(prefix="/ai-usage", tags=["AI 用量"])

SCENE_LABEL = {"chat": "对话问诊", "analyze": "四诊辨证"}


def _require_read(user: User) -> None:
    if not has_perm(user, "ai_usage:read"):
        raise HTTPException(status_code=403, detail="无权查看 AI 用量统计")


def _range(days: int) -> datetime:
    return datetime.now() - timedelta(days=days)


def _group(db: Session, col, since: datetime, extra_cols=()):
    """按某列分组聚合 calls / tokens / cost。"""
    cols = [col, *extra_cols]
    q = (
        db.query(
            *cols,
            func.count(AiUsageLog.id),
            func.coalesce(func.sum(AiUsageLog.total_tokens), 0),
            func.coalesce(func.sum(AiUsageLog.cost), 0.0),
        )
        .filter(AiUsageLog.created_at >= since)
        .group_by(*cols)
    )
    return q.all()


@router.get("/summary", summary="AI 用量汇总（卡片 / 趋势 / 分组）")
def ai_usage_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_read(current_user)
    since = _range(days)

    totals = db.query(
        func.count(AiUsageLog.id),
        func.coalesce(func.sum(AiUsageLog.prompt_tokens), 0),
        func.coalesce(func.sum(AiUsageLog.completion_tokens), 0),
        func.coalesce(func.sum(AiUsageLog.total_tokens), 0),
        func.coalesce(func.sum(AiUsageLog.cache_hit_tokens), 0),
        func.coalesce(func.sum(AiUsageLog.cost), 0.0),
    ).filter(AiUsageLog.created_at >= since).one()

    success_calls = (
        db.query(func.count(AiUsageLog.id))
        .filter(AiUsageLog.created_at >= since, AiUsageLog.success.is_(True))
        .scalar() or 0
    )
    calls = int(totals[0] or 0)

    # 按日趋势（补齐无数据的日期，前端可直接画连续柱状图）
    day_rows = (
        db.query(
            func.date(AiUsageLog.created_at),
            func.count(AiUsageLog.id),
            func.coalesce(func.sum(AiUsageLog.total_tokens), 0),
            func.coalesce(func.sum(AiUsageLog.cost), 0.0),
        )
        .filter(AiUsageLog.created_at >= since)
        .group_by(func.date(AiUsageLog.created_at))
        .all()
    )
    day_map = {str(r[0]): r for r in day_rows}
    trend = []
    for i in range(days):
        d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        r = day_map.get(d)
        trend.append({
            "date": d,
            "calls": int(r[1]) if r else 0,
            "tokens": int(r[2] or 0) if r else 0,
            "cost": round(float(r[3] or 0), 6) if r else 0.0,
        })

    by_model = [
        {
            "model": r[0] or "—",
            "is_vision": bool(r[1]),
            "calls": int(r[2]),
            "tokens": int(r[3] or 0),
            "cost": round(float(r[4] or 0), 6),
        }
        for r in _group(db, AiUsageLog.model, since, (AiUsageLog.is_vision,))
    ]
    by_scene = [
        {
            "scene": r[0] or "—",
            "scene_label": SCENE_LABEL.get(r[0], r[0] or "—"),
            "calls": int(r[1]),
            "tokens": int(r[2] or 0),
            "cost": round(float(r[3] or 0), 6),
        }
        for r in _group(db, AiUsageLog.scene, since)
    ]
    by_user = [
        {
            "username": r[0] or "—",
            "calls": int(r[1]),
            "tokens": int(r[2] or 0),
            "cost": round(float(r[3] or 0), 6),
        }
        for r in _group(db, AiUsageLog.username, since)
    ]
    by_model.sort(key=lambda x: x["cost"], reverse=True)
    by_user.sort(key=lambda x: x["cost"], reverse=True)

    return {
        "days": days,
        "pricing_configured": pricing_configured(),
        "totals": {
            "calls": calls,
            "success_calls": int(success_calls),
            "failed_calls": calls - int(success_calls),
            "prompt_tokens": int(totals[1] or 0),
            "completion_tokens": int(totals[2] or 0),
            "total_tokens": int(totals[3] or 0),
            "cache_hit_tokens": int(totals[4] or 0),
            "cost": round(float(totals[5] or 0), 6),
        },
        "trend": trend,
        "by_model": by_model,
        "by_scene": by_scene,
        "by_user": by_user,
    }


@router.get("/logs", summary="AI 用量明细分页")
def ai_usage_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    scene: str | None = None,
    model: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_read(current_user)
    q = db.query(AiUsageLog)
    if scene:
        q = q.filter(AiUsageLog.scene == scene)
    if model:
        q = q.filter(AiUsageLog.model == model)
    total = q.count()
    rows = (
        q.order_by(AiUsageLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "username": r.username,
                "scene": r.scene,
                "scene_label": SCENE_LABEL.get(r.scene or "", r.scene or "—"),
                "model": r.model,
                "is_vision": bool(r.is_vision),
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "cache_hit_tokens": r.cache_hit_tokens,
                "cost": round(float(r.cost or 0), 6),
                "success": bool(r.success),
                "error": r.error,
                "duration_ms": r.duration_ms,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/export", summary="导出 AI 用量明细 CSV")
def export_ai_usage(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_read(current_user)
    rows = (
        db.query(AiUsageLog)
        .filter(AiUsageLog.created_at >= _range(days))
        .order_by(AiUsageLog.id.desc())
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["时间", "账号", "场景", "模型", "Vision", "输入token", "输出token",
                "总token", "缓存命中token", "估算费用(元)", "成功", "错误", "耗时(ms)"])
    for r in rows:
        w.writerow([
            r.created_at.isoformat() if r.created_at else "",
            r.username or "", SCENE_LABEL.get(r.scene or "", r.scene or ""),
            r.model or "", "是" if r.is_vision else "否",
            r.prompt_tokens, r.completion_tokens, r.total_tokens, r.cache_hit_tokens,
            f"{float(r.cost or 0):.6f}", "是" if r.success else "否",
            r.error or "", r.duration_ms if r.duration_ms is not None else "",
        ])
    # BOM 保证 Excel 直接打开不乱码
    content = "\ufeff" + buf.getvalue()
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="ai-usage-{datetime.now():%Y%m%d}.csv"'},
    )


@router.delete("/logs", summary="清空 AI 用量记录（仅管理员）")
def clear_ai_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "system:write"):
        raise HTTPException(status_code=403, detail="仅管理员可清空 AI 用量记录")
    n = db.query(AiUsageLog).delete()
    db.commit()
    return {"deleted": n}
