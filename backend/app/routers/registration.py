"""挂号（前台分诊登记）路由：把「挂号 → 就诊 → 开方 → 收费」连成闭环。

挂号动作：登记/新建患者 + 创建就诊(Visit, 置待诊) + 生成挂号序号 + 记录挂号费(经收费单按 visit_id 关联)。
之后医生从队列「接诊」进入开方（PrescriptionEditor?visit_id=...），开方后走收费单，形成完整业务闭环。

权限：登记与状态变更需 patient:write；查看队列/详情需 patient:read。
"""
import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.user import User
from app.models.billing import Charge
from app.routers.auth import get_current_user
from app.permissions import has_perm
from app.schemas.billing import ChargeCreate, ChargeResponse
from app.schemas.patient import PatientCreate
from app.services.billing_service import (
    create_charge, refund_charge_record, cancel_charge_record, VALID_METHODS,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/registration", tags=["挂号"])


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class RegistrationCreate(BaseModel):
    patient_id: int | None = Field(default=None, description="选择已有患者")
    # 复用患者建档 schema，与「患者列表-新增患者」字段完全一致，保证挂号建档信息互通
    new_patient: PatientCreate | None = Field(default=None, description="或在挂号时新建患者")
    department: str | None = Field(default=None, description="科室/接诊医师")
    registration_fee: float = Field(default=0.0, ge=0, description="挂号费(元)")
    # 开单即收（前台直接收挂号费）
    payment_method: str | None = Field(default=None, description="收款方式")
    paid: float | None = Field(default=None, ge=0, description="实收金额(默认=挂号费)")
    force: bool = Field(default=False, description="该患者今日已挂号时，前台确认后强制再挂")


class RegistrationUpdate(BaseModel):
    status: str | None = Field(default=None, description="就诊状态: 待诊/已接诊/已完成/已取消")
    department: str | None = Field(default=None, description="科室/接诊医师")


def _serialize_visit(v: Visit, patient_name: str | None) -> dict:
    return {
        "id": v.id,
        "patient_id": v.patient_id,
        "patient_name": patient_name,
        "visit_date": v.visit_date,
        "visit_type": v.visit_type,
        "chief_complaint": v.chief_complaint,
        "queue_no": v.queue_no,
        "registration_fee": float(v.registration_fee) if v.registration_fee is not None else None,
        "registered_at": v.registered_at.isoformat() if v.registered_at else None,
        "registrar_id": v.registrar_id,
        "department": v.department,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _next_queue_no(db: Session, day: str) -> int:
    row = (
        db.query(func.max(Visit.queue_no))
        .filter(
            Visit.registered_at.isnot(None),
            Visit.registered_at >= day + " 00:00:00",
            Visit.registered_at < day + " 23:59:59",
        )
        .first()
    )
    return (row[0] or 0) + 1


def _active_registration_today(db: Session, patient_id: int, day: str) -> Visit | None:
    """查该患者今日未取消的挂号，避免误操作重复挂号、重复收挂号费。"""
    return (
        db.query(Visit)
        .filter(
            Visit.patient_id == patient_id,
            Visit.visit_date == day,
            Visit.registered_at.isnot(None),
            Visit.status != "已取消",
        )
        .order_by(Visit.id.desc())
        .first()
    )


def _settle_visit_charges(db: Session, visit_id: int, current_user: User) -> int:
    """退号联动：该就诊下**所有**在账收费单（挂号费 + 处方收费）一并结算。

    已收的全额退、待收的作废，钱不留在账上。此前只看挂号费，患者退号后
    处方收费仍挂在账上，是收费台最容易被投诉的漏洞。返回处理数供前台提示。
    """
    charges = (
        db.query(Charge)
        .filter(Charge.visit_id == visit_id, Charge.status.in_(("待收费", "已收费")))
        .all()
    )
    handled = 0
    for ch in charges:
        if ch.status == "已收费":
            refund_charge_record(ch, None, f"退号自动退费（就诊 #{visit_id}）", current_user)
            handled += 1
        elif ch.status == "待收费":
            cancel_charge_record(ch, f"退号自动作废待收单（就诊 #{visit_id}）", current_user)
            handled += 1
    return handled


# 就诊状态单向流转：禁止回跳（尤其「已完成 → 已取消」会二次触发退挂号费）
ALLOWED_VISIT_TRANSITIONS = {
    "待诊": ("待诊", "已接诊", "已取消"),
    "已接诊": ("已完成", "已取消", "已接诊"),
    "已完成": ("已完成",),
    "已取消": ("已取消",),
}


@router.post("", summary="挂号登记（新建/选择患者 + 创建就诊 + 收挂号费）")
def register(
    payload: RegistrationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not has_perm(current_user, "patient:write"):
        raise HTTPException(status_code=403, detail="无权进行挂号登记")

    day = _today()
    # 同日重复挂号：先提示前台，确认后以 force=True 放行，避免误点产生两条就诊 + 两张挂号费单
    duplicate_of = None
    if payload.patient_id:
        dup = _active_registration_today(db, payload.patient_id, day)
        if dup:
            if not payload.force:
                raise HTTPException(
                    status_code=409,
                    detail=f"该患者今日已挂号（队列号 {dup.queue_no}），请确认是否仍要挂号",
                )
            duplicate_of = dup.id  # force 放行：回传前一次就诊，提醒前台核对是否重复收挂号费

    # 「患者 + 就诊 + 挂号费收费单」在**同一事务**内提交（服务层 commit=False）。
    # 排队号由 (visit_date, queue_no) 唯一约束兜底，并发撞号时整体回滚重试，
    # 杜绝「收费单已提交、就诊记录没落地」的孤儿数据。
    for attempt in range(3):
        try:
            # 1) 解析患者
            patient = None
            if payload.patient_id:
                patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
                if not patient:
                    raise HTTPException(status_code=404, detail="患者不存在")
            elif payload.new_patient:
                patient = Patient(**payload.new_patient.model_dump())
                db.add(patient)
                db.flush()
            else:
                raise HTTPException(status_code=400, detail="请提供 patient_id 或 new_patient")

            # 2) 创建就诊（待诊）+ 挂号序号
            visit = Visit(
                patient_id=patient.id,
                visit_date=day,
                visit_type="初诊",
                chief_complaint="（待接诊）",
                status="待诊",
                queue_no=_next_queue_no(db, day),
                registered_at=datetime.now(),
                registrar_id=current_user.id,
                department=payload.department,
                registration_fee=Decimal(str(payload.registration_fee)) if payload.registration_fee else None,
            )
            db.add(visit)
            db.flush()

            # 3) 挂号费：同一事务内开单，不自行提交
            charge = None
            if payload.registration_fee > 0:
                if payload.payment_method and payload.payment_method not in VALID_METHODS:
                    raise HTTPException(status_code=400, detail="无效的收款方式")
                cc = ChargeCreate(
                    kind="registration",
                    visit_id=visit.id,
                    patient_id=patient.id,
                    amount=payload.registration_fee,
                    patient_name=patient.name,
                    title="挂号费",
                    note=f"挂号费（{payload.department or '门诊'}）",
                    payment_method=payload.payment_method,
                    paid=payload.paid if payload.paid is not None else payload.registration_fee,
                )
                charge = create_charge(db, cc, current_user, commit=False)

            db.commit()
            db.refresh(visit)
            if charge is not None:
                db.refresh(charge)
            return {
                "visit": _serialize_visit(visit, patient.name),
                "charge": ChargeResponse.model_validate(charge).model_dump() if charge else None,
                "duplicate_of": duplicate_of,
            }
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise HTTPException(status_code=409, detail="挂号序号冲突，请稍后重试")
        except Exception:
            db.rollback()
            raise


@router.get("/queue", summary="今日挂号队列")
def queue(
    day: str | None = Query(default=None, description="日期 yyyy-mm-dd，默认今天"),
    status: str | None = Query(default=None, description="状态筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "patient:read"):
        raise HTTPException(status_code=403, detail="无权查看挂号队列")
    day = day or _today()
    q = (
        db.query(Visit, Patient.name)
        .join(Patient, Patient.id == Visit.patient_id)
        .filter(
            Visit.registered_at.isnot(None),
            Visit.registered_at >= day + " 00:00:00",
            Visit.registered_at < day + " 23:59:59",
        )
    )
    if status:
        q = q.filter(Visit.status == status)
    rows = q.order_by(Visit.queue_no.asc()).all()

    items = []
    for v, pname in rows:
        d = _serialize_visit(v, pname)
        ch = (
            db.query(Charge)
            .filter(Charge.visit_id == v.id, Charge.kind == "registration")
            .order_by(Charge.id.desc())
            .first()
        )
        d["registration_charge"] = ChargeResponse.model_validate(ch).model_dump() if ch else None
        items.append(d)
    return {"items": items, "date": day}


@router.get("/{visit_id}", summary="挂号/就诊详情（含收费单）")
def visit_detail(visit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not has_perm(current_user, "patient:read"):
        raise HTTPException(status_code=403, detail="无权查看就诊详情")
    v = db.query(Visit).filter(Visit.id == visit_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    pat = db.query(Patient).filter(Patient.id == v.patient_id).first()
    d = _serialize_visit(v, pat.name if pat else None)
    charges = db.query(Charge).filter(Charge.visit_id == v.id).all()
    d["charges"] = [ChargeResponse.model_validate(c).model_dump() for c in charges]
    return d


@router.patch("/{visit_id}", summary="更新就诊状态/科室（接诊/完成/取消）")
def update_registration(
    visit_id: int,
    payload: RegistrationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_perm(current_user, "patient:write"):
        raise HTTPException(status_code=403, detail="无权变更就诊状态")
    v = db.query(Visit).filter(Visit.id == visit_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    if payload.status is not None:
        if payload.status not in ("待诊", "已接诊", "已完成", "已取消"):
            raise HTTPException(status_code=400, detail="无效的就诊状态")
        # 状态单向流转，禁止回跳（已完成/已取消为终态）
        if payload.status not in ALLOWED_VISIT_TRANSITIONS.get(v.status or "", ()):
            raise HTTPException(
                status_code=400,
                detail=f"就诊状态不可从「{v.status}」变更为「{payload.status}」",
            )
        # 退号联动：该就诊下挂号费 + 处方收费单全部结算，钱不留在账上
        if payload.status == "已取消" and v.status != "已取消":
            _settle_visit_charges(db, v.id, current_user)
        v.status = payload.status
    if payload.department is not None:
        v.department = payload.department
    db.commit()
    db.refresh(v)
    pat = db.query(Patient).filter(Patient.id == v.patient_id).first()
    return _serialize_visit(v, pat.name if pat else None)


@router.post("/{visit_id}/call", summary="叫号/接诊（待诊 -> 已接诊）")
def call_visit(visit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return update_registration(visit_id, RegistrationUpdate(status="已接诊"), db, current_user)


@router.post("/{visit_id}/complete", summary="完成就诊（已接诊 -> 已完成）")
def complete_visit(visit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return update_registration(visit_id, RegistrationUpdate(status="已完成"), db, current_user)
