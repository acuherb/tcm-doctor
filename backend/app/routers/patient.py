"""患者管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.inquiry import InquiryRecord
from app.models.followup import FollowUp
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.patient import (
    PatientCreate, PatientUpdate, PatientResponse, PatientListResponse,
    VisitCreate, VisitUpdate, VisitResponse, ConstitutionSubmit, ConstitutionResult,
    InquiryRecordOut, FollowUpCreate, FollowUpUpdate, FollowUpResponse,
)

router = APIRouter(prefix="/patients", tags=["患者管理"])


# ── 患者 CRUD ──

@router.get("", response_model=PatientListResponse, summary="患者列表")
def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="搜索(姓名/电话)"),
    constitution_type: str | None = Query(None, description="按体质类型筛选"),
    tag: str | None = Query(None, description="按患者标签筛选"),
    has_allergy: bool | None = Query(None, description="有无过敏史: true/false"),
    improvement: str | None = Query(None, description="按最近一次随访改善程度筛选"),
    sort_by: str | None = Query(None, description="排序字段: last_visit_date(按最近就诊)"),
    order: str = Query("desc", description="排序方向: desc/asc"),
    db: Session = Depends(get_db),
):
    from datetime import date
    from sqlalchemy import or_

    from app.models.followup import FollowUp
    from app.models.visit import Visit

    query = db.query(Patient)
    if search:
        query = query.filter((Patient.name.contains(search)) | (Patient.phone.contains(search)))
    if constitution_type:
        query = query.filter(Patient.constitution_type == constitution_type)
    if has_allergy is True:
        query = query.filter(Patient.allergy_history.isnot(None), Patient.allergy_history != "")
    elif has_allergy is False:
        query = query.filter(or_(Patient.allergy_history == None, Patient.allergy_history == ""))

    # 单诊所数据量有限，拉取匹配集合后在 Python 侧做聚合/筛选/排序（避免复杂 SQL 子查询）
    candidates = query.all()
    ids = [p.id for p in candidates]
    visits = db.query(Visit).filter(Visit.patient_id.in_(ids)).all() if ids else []
    followups = db.query(FollowUp).filter(FollowUp.patient_id.in_(ids)).all() if ids else []
    visits_by_p: dict[int, list] = {}
    for v in visits:
        visits_by_p.setdefault(v.patient_id, []).append(v)
    fups_by_p: dict[int, list] = {}
    for f in followups:
        fups_by_p.setdefault(f.patient_id, []).append(f)

    today = date.today()
    enriched = []
    for p in candidates:
        pv = sorted(visits_by_p.get(p.id, []), key=lambda x: x.visit_date or "")
        pf = sorted(fups_by_p.get(p.id, []), key=lambda x: x.followup_date or "")
        last_visit_date = pv[-1].visit_date if pv else None
        last_fu = pf[-1] if pf else None
        last_improvement = last_fu.improvement if last_fu else None
        days_since = None
        if last_visit_date:
            try:
                days_since = (today - date.fromisoformat(str(last_visit_date)[:10])).days
            except Exception:
                days_since = None
        # 在治/停诊 启发式：最近改善为好转类→在治；反复/加重→停诊；无随访→新诊/未复诊
        if last_improvement in ("明显好转", "好转", "稳定"):
            active_status = "在治"
        elif last_improvement in ("反复", "加重"):
            active_status = "停诊"
        elif last_visit_date:
            active_status = "未复诊"
        else:
            active_status = "新诊"
        # 附加聚合字段（Pydantic from_attributes 会拾取）
        p.last_visit_date = last_visit_date
        p.days_since_visit = days_since
        p.last_improvement = last_improvement
        p.active_status = active_status
        enriched.append(p)

    # 标签（JSON 列表，Python 侧精确匹配）
    if tag:
        enriched = [p for p in enriched if tag in (p.tags or [])]
    # 最近改善筛选
    if improvement:
        enriched = [p for p in enriched if p.last_improvement == improvement]
    # 排序
    if sort_by == "last_visit_date":
        enriched.sort(key=lambda x: x.last_visit_date or "", reverse=(order != "asc"))
    else:
        enriched.sort(key=lambda x: str(x.updated_at or ""), reverse=True)

    total = len(enriched)
    start = (page - 1) * page_size
    items = enriched[start : start + page_size]
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
    from app.models.followup import FollowUp

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

    # 4.5) 病情跟踪
    db.query(FollowUp).filter(FollowUp.patient_id == patient_id).delete(synchronize_session=False)

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


@router.put("/{patient_id}/visits/{visit_id}", response_model=VisitResponse, summary="更新就诊记录")
def update_visit(
    patient_id: int,
    visit_id: int,
    data: VisitUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新就诊记录 — 支持完善 AI 辨证分析 / 四诊信息，避免重复新建就诊"""
    visit = db.query(Visit).filter(Visit.id == visit_id, Visit.patient_id == patient_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(visit, k, v)
    db.commit()
    db.refresh(visit)
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
    # 一次就诊只有一次问诊十问：相同 (patient_id, visit_id) 已存在则更新，避免重复录入
    if data.visit_id is not None:
        existing = (
            db.query(InquiryRecord)
            .filter(InquiryRecord.patient_id == patient_id, InquiryRecord.visit_id == data.visit_id)
            .order_by(InquiryRecord.created_at.desc())
            .first()
        )
    else:
        existing = (
            db.query(InquiryRecord)
            .filter(InquiryRecord.patient_id == patient_id, InquiryRecord.visit_id.is_(None))
            .order_by(InquiryRecord.created_at.desc())
            .first()
        )
    if existing:
        existing.primary_type = result_dict["primary_type"]
        existing.answers = data.answers
        existing.notes = data.notes
        existing.result = result_dict
    else:
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
            primary_meridians=stored.get("primary_meridians") or [],
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


# ── 病情跟踪（治疗后效果反馈/随访） ──

@router.get("/{patient_id}/followups", response_model=list[FollowUpResponse], summary="病情跟踪列表")
def list_followups(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return db.query(FollowUp).filter(FollowUp.patient_id == patient_id).order_by(FollowUp.followup_date.desc()).all()


@router.post("/{patient_id}/followups", response_model=FollowUpResponse, summary="新增病情跟踪")
def create_followup(patient_id: int, data: FollowUpCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    fu = FollowUp(patient_id=patient_id, **data.model_dump())
    db.add(fu)
    db.commit()
    db.refresh(fu)
    return fu


@router.put("/{patient_id}/followups/{fu_id}", response_model=FollowUpResponse, summary="更新病情跟踪")
def update_followup(patient_id: int, fu_id: int, data: FollowUpUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fu = db.query(FollowUp).filter(FollowUp.id == fu_id, FollowUp.patient_id == patient_id).first()
    if not fu:
        raise HTTPException(status_code=404, detail="病情跟踪记录不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(fu, k, v)
    db.commit()
    db.refresh(fu)
    return fu


@router.delete("/{patient_id}/followups/{fu_id}", summary="删除病情跟踪")
def delete_followup(patient_id: int, fu_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fu = db.query(FollowUp).filter(FollowUp.id == fu_id, FollowUp.patient_id == patient_id).first()
    if not fu:
        raise HTTPException(status_code=404, detail="病情跟踪记录不存在")
    db.delete(fu)
    db.commit()
    return {"detail": "已删除"}