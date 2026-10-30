"""随访提醒路由 —— 列表/创建/标记完成/取消/删除"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.followup_reminder import FollowUpReminder
from app.models.patient import Patient
from app.routers.auth import get_current_user
from app.models.user import User
from app.schemas.followup_reminder import (
    FollowUpReminderCreate,
    FollowUpReminderUpdate,
    FollowUpReminderResponse,
)

router = APIRouter(prefix="/followup-reminders", tags=["随访提醒"])


def _serialize(r: FollowUpReminder, patient_name: str | None = None, overdue: bool = False) -> FollowUpReminderResponse:
    d = FollowUpReminderResponse.model_validate(r)
    d.patient_name = patient_name
    d.overdue = overdue
    return d


@router.post("", response_model=FollowUpReminderResponse, summary="创建随访提醒（手动）")
def create_reminder(
    data: FollowUpReminderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.query(Patient).filter(Patient.id == data.patient_id).first():
        raise HTTPException(status_code=404, detail="患者不存在")
    r = FollowUpReminder(
        patient_id=data.patient_id,
        due_date=data.due_date,
        note=data.note,
        source_type=data.source_type,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _serialize(r)


@router.get("", response_model=list[FollowUpReminderResponse], summary="随访提醒列表")
def list_reminders(
    patient_id: int | None = Query(None, description="按患者筛选"),
    status: str | None = Query(None, description="pending/done/cancelled"),
    due_before: str | None = Query(None, description="应回访日期 <= (含) YYYY-MM-DD"),
    due_after: str | None = Query(None, description="应回访日期 >= (含) YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    q = db.query(FollowUpReminder)
    if patient_id is not None:
        q = q.filter(FollowUpReminder.patient_id == patient_id)
    if status:
        q = q.filter(FollowUpReminder.status == status)
    if due_before:
        q = q.filter(FollowUpReminder.due_date <= due_before)
    if due_after:
        q = q.filter(FollowUpReminder.due_date >= due_after)
    rows = q.order_by(FollowUpReminder.due_date).all()

    pids = {r.patient_id for r in rows}
    pmap = {p.id: p.name for p in db.query(Patient).filter(Patient.id.in_(pids)).all()} if pids else {}
    today = date.today().isoformat()
    return [
        _serialize(r, pmap.get(r.patient_id), r.due_date < today and r.status == "pending")
        for r in rows
    ]


@router.patch("/{rid}", response_model=FollowUpReminderResponse, summary="更新随访提醒（标记完成/取消/改期）")
def update_reminder(rid: int, data: FollowUpReminderUpdate, db: Session = Depends(get_db)):
    r = db.query(FollowUpReminder).filter(FollowUpReminder.id == rid).first()
    if not r:
        raise HTTPException(status_code=404, detail="提醒不存在")
    if data.status is not None:
        r.status = data.status
    if data.due_date is not None:
        r.due_date = data.due_date
    if data.note is not None:
        r.note = data.note
    db.commit()
    db.refresh(r)
    return _serialize(r)


@router.delete("/{rid}", summary="删除随访提醒")
def delete_reminder(rid: int, db: Session = Depends(get_db)):
    r = db.query(FollowUpReminder).filter(FollowUpReminder.id == rid).first()
    if not r:
        raise HTTPException(status_code=404, detail="提醒不存在")
    db.delete(r)
    db.commit()
    return {"ok": True}
