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
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.user import User
from app.models.billing import Charge
from app.routers.auth import get_current_user
from app.permissions import has_perm
from app.schemas.billing import ChargeCreate, ChargeResponse
from app.services.billing_service import create_charge, VALID_METHODS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/registration", tags=["挂号"])


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class NewPatientMini(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="姓名")
    phone: str | None = Field(None, description="电话")
    gender: str | None = Field(None, description="性别")
    birth_date: str | None = Field(None, description="出生日期")


class RegistrationCreate(BaseModel):
    patient_id: int | None = Field(default=None, description="选择已有患者")
    new_patient: NewPatientMini | None = Field(default=None, description="或在挂号时新建患者")
    department: str | None = Field(default=None, description="科室/接诊医师")
    registration_fee: float = Field(default=0.0, ge=0, description="挂号费(元)")
    # 开单即收（前台直接收挂号费）
    payment_method: str | None = Field(default=None, description="收款方式")
    paid: float | None = Field(default=None, ge=0, description="实收金额(默认=挂号费)")


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


@router.post("", summary="挂号登记（新建/选择患者 + 创建就诊 + 收挂号费）")
def register(
    payload: RegistrationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not has_perm(current_user, "patient:write"):
        raise HTTPException(status_code=403, detail="无权进行挂号登记")

    # 1) 解析患者
    patient = None
    if payload.patient_id:
        patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="患者不存在")
    elif payload.new_patient:
        patient = Patient(
            name=payload.new_patient.name,
            phone=payload.new_patient.phone,
            gender=payload.new_patient.gender,
            birth_date=payload.new_patient.birth_date,
        )
        db.add(patient)
        db.flush()
    else:
        raise HTTPException(status_code=400, detail="请提供 patient_id 或 new_patient")

    # 2) 创建就诊（待诊）+ 挂号序号
    day = _today()
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

    # 3) 挂号费：开单即收或留待收费（在收费台收取）
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
        charge = create_charge(db, cc, current_user)

    db.commit()
    db.refresh(visit)
    return {
        "visit": _serialize_visit(visit, patient.name),
        "charge": ChargeResponse.model_validate(charge).model_dump() if charge else None,
    }


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
