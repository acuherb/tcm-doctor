"""排班路由 — 固定排班表（医生 × 日期 × 时段）的增删改查与按周维护。

权限：读需 schedule:read，写（增/改/删/按周保存/复制）需 schedule:write；
网关中间件已按 DOMAIN_PERMS 统一校验，此处对写操作再做一次显式兜底。
"""
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.schedule import Schedule, ScheduleState
from app.permissions import has_perm
from app.routers.auth import get_current_user

router = APIRouter(prefix="/schedule", tags=["排班"])

VALID_PERIODS = ("morning", "afternoon", "full")
PERIOD_LABEL = {"morning": "上午", "afternoon": "下午", "full": "全天"}


def _mark_enabled(db: Session) -> None:
    """标记「已启用排班」。整周全员休诊时 schedules 表会空，必须靠此标记维持约束。"""
    state = db.query(ScheduleState).filter(ScheduleState.id == 1).first()
    if state is None:
        db.add(ScheduleState(id=1, enabled=True))
    elif not state.enabled:
        state.enabled = True


def _appointable(u: User) -> bool:
    """可排班的接诊账号：启用，且角色为医生/管理员。"""
    return bool(u.is_active and (u.is_admin or u.role in ("doctor", "admin")))


def _parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")


def _serialize(s: Schedule, doctor_name: str | None = None) -> dict:
    return {
        "id": s.id,
        "doctor_id": s.doctor_id,
        "doctor_name": doctor_name,
        "schedule_date": s.schedule_date.isoformat(),
        "period": s.period,
        "period_label": PERIOD_LABEL.get(s.period, s.period),
        "department": s.department,
        "note": s.note,
    }


# ── 医生列表（排班编辑器使用，不受「当日出诊」过滤，列出全部可排班账号）──
@router.get("/doctors", summary="可排班医师列表")
def list_doctors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "schedule:read"):
        raise HTTPException(status_code=403, detail="无权查看排班")
    users = db.query(User).filter(User.is_active.is_(True)).order_by(User.id).all()
    return [
        {
            "id": u.id,
            "name": u.display_name or u.username,
            "department": (u.department or "").strip(),
        }
        for u in users
        if _appointable(u)
    ]


# ── 按周查询：返回该周（start 起 7 天）的排班条目 ──
@router.get("/week", summary="按周排班（返回某周 7 天条目）")
def week_schedule(
    start: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "schedule:read"):
        raise HTTPException(status_code=403, detail="无权查看排班")
    monday = _parse_date(start)
    sunday = monday + timedelta(days=6)
    rows = (
        db.query(Schedule)
        .filter(Schedule.schedule_date >= monday, Schedule.schedule_date <= sunday)
        .all()
    )
    doctor_ids = {r.doctor_id for r in rows}
    names = {
        u.id: (u.display_name or u.username)
        for u in db.query(User).filter(User.id.in_(doctor_ids)).all()
    }
    return {
        "start": monday.isoformat(),
        "end": sunday.isoformat(),
        "items": [_serialize(r, names.get(r.doctor_id)) for r in rows],
    }


class WeekSaveItem(BaseModel):
    doctor_id: int
    date: str
    period: str


class WeekSaveBody(BaseModel):
    start: str
    items: list[WeekSaveItem] = []


# ── 按周保存：以 start 所在周为范围，整周全量覆盖后批量写入（幂等）──
@router.post("/week", summary="保存整周排班")
def save_week(
    body: WeekSaveBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "schedule:write"):
        raise HTTPException(status_code=403, detail="无权维护排班")
    monday = _parse_date(body.start)
    sunday = monday + timedelta(days=6)
    doctor_ids = {it.doctor_id for it in body.items}

    # 校验医生均为可排班账号
    users = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(doctor_ids)).all()
        if _appointable(u)
    }
    for it in body.items:
        if it.doctor_id not in users:
            raise HTTPException(status_code=400, detail=f"医师 {it.doctor_id} 不存在、已停用或非医生账号")
        if it.period not in VALID_PERIODS:
            raise HTTPException(status_code=400, detail=f"时段 {it.period} 非法（应为 morning/afternoon/full）")

    # 整周全量覆盖：前端提交的是整张网格，休诊格不产生 item。
    # 因此必须先清空「该周全部」排班（不能只删 items 里出现的医生，否则
    # 把某医生整周改为休诊时其旧记录会残留 → 休诊永远改不掉、挂号仍能选到他）。
    deleted = (
        db.query(Schedule)
        .filter(
            Schedule.schedule_date >= monday,
            Schedule.schedule_date <= sunday,
        )
        .delete()
    )
    created = 0
    for it in body.items:
        d = _parse_date(it.date)
        if not (monday <= d <= sunday):
            raise HTTPException(status_code=400, detail="条目日期不在所选周内")
        u = users[it.doctor_id]
        db.add(
            Schedule(
                doctor_id=u.id,
                schedule_date=d,
                period=it.period,
                department=(u.department or "").strip() or None,
            )
        )
        created += 1
    _mark_enabled(db)
    db.commit()
    return {"deleted": deleted, "created": created}


class CopyWeekBody(BaseModel):
    source_start: str
    target_start: str


# ── 复制上周：把 source 周排班整体搬移到 target 周（覆盖 target 周）──
@router.post("/copy-week", summary="复制某周排班到另一周")
def copy_week(
    body: CopyWeekBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "schedule:write"):
        raise HTTPException(status_code=403, detail="无权维护排班")
    src = _parse_date(body.source_start)
    tgt = _parse_date(body.target_start)
    src_end = src + timedelta(days=6)
    tgt_end = tgt + timedelta(days=6)
    shift = tgt - src  # 通常为 7 天

    rows = (
        db.query(Schedule)
        .filter(Schedule.schedule_date >= src, Schedule.schedule_date <= src_end)
        .all()
    )
    doctor_ids = {r.doctor_id for r in rows}
    # 覆盖目标周：先清空目标周这些医生的排班
    deleted = (
        db.query(Schedule)
        .filter(
            Schedule.doctor_id.in_(doctor_ids),
            Schedule.schedule_date >= tgt,
            Schedule.schedule_date <= tgt_end,
        )
        .delete()
    )
    copied = 0
    for r in rows:
        new_date = r.schedule_date + shift
        if not (tgt <= new_date <= tgt_end):
            continue
        db.add(
            Schedule(
                doctor_id=r.doctor_id,
                schedule_date=new_date,
                period=r.period,
                department=r.department,
            )
        )
        copied += 1
    _mark_enabled(db)
    db.commit()
    return {"deleted": deleted, "copied": copied}


class ScheduleCreate(BaseModel):
    doctor_id: int
    schedule_date: str
    period: str
    note: str | None = None


# ── 单条 upsert ──
@router.post("", summary="新增/更新单条排班")
def upsert_schedule(
    body: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "schedule:write"):
        raise HTTPException(status_code=403, detail="无权维护排班")
    u = db.query(User).filter(User.id == body.doctor_id).first()
    if not u or not _appointable(u):
        raise HTTPException(status_code=400, detail="指定的医师不存在、已停用或非医生账号")
    if body.period not in VALID_PERIODS:
        raise HTTPException(status_code=400, detail="时段非法（应为 morning/afternoon/full）")
    d = _parse_date(body.schedule_date)
    existing = (
        db.query(Schedule)
        .filter(
            Schedule.doctor_id == body.doctor_id,
            Schedule.schedule_date == d,
            Schedule.period == body.period,
        )
        .first()
    )
    if existing:
        existing.department = (u.department or "").strip() or None
        existing.note = body.note
        s = existing
    else:
        s = Schedule(
            doctor_id=u.id,
            schedule_date=d,
            period=body.period,
            department=(u.department or "").strip() or None,
            note=body.note,
        )
        db.add(s)
    _mark_enabled(db)
    db.commit()
    db.refresh(s)
    return _serialize(s, u.display_name or u.username)


class ScheduleUpdate(BaseModel):
    period: str | None = None
    note: str | None = None


@router.put("/{schedule_id}", summary="更新排班（时段/备注）")
def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "schedule:write"):
        raise HTTPException(status_code=403, detail="无权维护排班")
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="排班记录不存在")
    if body.period is not None:
        if body.period not in VALID_PERIODS:
            raise HTTPException(status_code=400, detail="时段非法（应为 morning/afternoon/full）")
        s.period = body.period
    if body.note is not None:
        s.note = body.note
    db.commit()
    db.refresh(s)
    u = db.query(User).filter(User.id == s.doctor_id).first()
    return _serialize(s, u.display_name or u.username if u else None)


@router.delete("/{schedule_id}", summary="删除排班（休诊）")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "schedule:write"):
        raise HTTPException(status_code=403, detail="无权维护排班")
    n = db.query(Schedule).filter(Schedule.id == schedule_id).delete()
    if not n:
        raise HTTPException(status_code=404, detail="排班记录不存在")
    db.commit()
    return {"deleted": n}
