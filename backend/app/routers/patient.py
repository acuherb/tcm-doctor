"""患者管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.inquiry import InquiryRecord
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.patient import (
    PatientCreate, PatientUpdate, PatientResponse, PatientListResponse,
    VisitCreate, VisitResponse, ConstitutionSubmit, ConstitutionResult,
    InquiryRecordOut,
)

router = APIRouter(prefix="/patients", tags=["患者管理"])


# ── 患者 CRUD ──

@router.get("", response_model=PatientListResponse, summary="患者列表")
def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="搜索(姓名/电话)"),
    db: Session = Depends(get_db),
):
    query = db.query(Patient)
    if search:
        query = query.filter(
            (Patient.name.contains(search)) | (Patient.phone.contains(search))
        )
    total = query.count()
    items = query.order_by(Patient.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PatientListResponse(total=total, items=items, page=page, page_size=page_size)


@router.post("", response_model=PatientResponse, summary="新增患者")
def create_patient(data: PatientCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = Patient(**data.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientResponse, summary="患者详情")
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return patient


@router.put("/{patient_id}", response_model=PatientResponse, summary="更新患者")
def update_patient(patient_id: int, data: PatientUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, key, value)
    db.commit()
    db.refresh(patient)
    return patient


@router.delete("/{patient_id}", summary="删除患者")
def delete_patient(patient_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")

    # 显式级联清理所有子表，避免遗留孤儿记录。
    # 原因：Patient 仅对 visits 配置了 ORM 级联，问诊十问 / 会话等并无级联；
    # 而 SQLite 删除行后会复用 id，若不清理，重建同名患者时旧记录会回流到新患者。
    from app.models.prescription import (
        Prescription, PrescriptionItem, AcupointPrescription, PrescriptionInjection,
    )
    from app.models.conversation import Conversation, Message

    # 1) 处方明细 → 处方（需在就诊记录之前，因处方外键指向就诊）
    pres_ids = db.query(Prescription.id).filter(Prescription.patient_id == patient_id)
    db.query(PrescriptionItem).filter(PrescriptionItem.prescription_id.in_(pres_ids)).delete(synchronize_session=False)
    db.query(AcupointPrescription).filter(AcupointPrescription.prescription_id.in_(pres_ids)).delete(synchronize_session=False)
    db.query(PrescriptionInjection).filter(PrescriptionInjection.prescription_id.in_(pres_ids)).delete(synchronize_session=False)
    db.query(Prescription).filter(Prescription.patient_id == patient_id).delete(synchronize_session=False)

    # 2) 问诊十问（外键指向就诊，需在就诊之前清理）
    db.query(InquiryRecord).filter(InquiryRecord.patient_id == patient_id).delete(synchronize_session=False)

    # 3) 智能问诊：消息 → 会话
    conv_ids = db.query(Conversation.id).filter(Conversation.patient_id == patient_id)
    db.query(Message).filter(Message.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
    db.query(Conversation).filter(Conversation.patient_id == patient_id).delete(synchronize_session=False)

    # 4) 就诊记录
    db.query(Visit).filter(Visit.patient_id == patient_id).delete(synchronize_session=False)

    # 5) 患者本身
    db.query(Patient).filter(Patient.id == patient_id).delete(synchronize_session=False)

    db.commit()
    return {"message": "删除成功"}


# ── 就诊记录 ──

@router.get("/{patient_id}/visits", response_model=list[VisitResponse], summary="就诊记录列表")
def list_visits(patient_id: int, db: Session = Depends(get_db)):
    visits = db.query(Visit).filter(Visit.patient_id == patient_id).order_by(Visit.visit_date.desc()).all()
    return visits


@router.post("/{patient_id}/visits", response_model=VisitResponse, summary="新增就诊记录")
def create_visit(patient_id: int, data: VisitCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    visit = Visit(patient_id=patient_id, **data.model_dump())
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


@router.get("/{patient_id}/visits/{visit_id}", response_model=VisitResponse, summary="就诊详情")
def get_visit(patient_id: int, visit_id: int, db: Session = Depends(get_db)):
    visit = db.query(Visit).filter(Visit.id == visit_id, Visit.patient_id == patient_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    return visit


# ── 体质辨识 ──

@router.post("/{patient_id}/constitution", response_model=ConstitutionResult, summary="提交体质辨识")
def submit_constitution(patient_id: int, data: ConstitutionSubmit, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")

    from app.services.constitution_evaluator import evaluate_constitution
    result_dict = evaluate_constitution(data.answers, data.notes)

    patient.constitution_type = result_dict["primary_type"]
    patient.constitution_score = result_dict  # 存完整推理结果，供报告还原
    db.add(patient)

    # 存档问诊十问，形成病例信息链
    record = InquiryRecord(
        patient_id=patient_id,
        visit_id=data.visit_id,
        primary_type=result_dict["primary_type"],
        answers=data.answers,
        notes=data.notes,
        result=result_dict,
    )
    db.add(record)
    db.commit()

    return ConstitutionResult(**result_dict)


@router.get("/{patient_id}/inquiries", response_model=list[InquiryRecordOut], summary="问诊十问记录列表")
def get_inquiries(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return db.query(InquiryRecord).filter(
        InquiryRecord.patient_id == patient_id
    ).order_by(InquiryRecord.created_at.desc()).all()


@router.get("/{patient_id}/constitution", response_model=ConstitutionResult | None, summary="获取体质报告")
def get_constitution(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    if not patient.constitution_type:
        return None
    stored = patient.constitution_score or {}
    if isinstance(stored, dict) and stored.get("findings") is not None:
        # 新格式：完整推理结果已存于 constitution_score
        return ConstitutionResult(
            primary_type=stored.get("primary_type") or patient.constitution_type,
            scores=stored.get("scores") or {},
            secondary_types=stored.get("secondary_types") or [],
            findings=stored.get("findings") or [],
            suggestion=stored.get("suggestion") or "",
            detail=stored.get("detail") or {},
        )
    # 兼容旧格式
    return ConstitutionResult(
        primary_type=patient.constitution_type,
        scores=stored or {},
        secondary_types=[],
        suggestion="",
    )