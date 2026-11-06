"""挂号（前台分诊登记）路由：把「挂号 → 就诊 → 开方 → 收费」连成闭环。

挂号动作：登记/新建患者 + 创建就诊(Visit, 置待诊，主诉为占位符) + 生成挂号序号
+ 记录挂号费(经收费单按 visit_id 关联)。

正确链路：队列「接诊」→ 患者详情自动打开**本次就诊**的编辑抽屉（不是直接跳开方页）
→ 医生写主诉/四诊/辨证（保存病历即自动推进「已接诊」）→ 抽屉内「去开药」进开方页
→ 收费 → 队列「完成」。

状态不再纯靠按钮：能否「完成」由业务事实（本次是否有真实病历、处方收款/发药情况）决定；
误点「接诊/完成」可经 /revert 受控回退并写审计日志（钱和药一动即禁止回退）。

权限：登记与状态变更需 patient:write；查看队列/详情需 patient:read。
"""
import logging
from datetime import datetime, date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.user import User
from app.models.billing import Charge
from app.models.prescription import Prescription
from app.models.schedule import Schedule
from app.routers.auth import get_current_user
from app.permissions import has_perm
from app.schemas.billing import ChargeCreate, ChargeResponse
from app.schemas.patient import PatientCreate
from app.services.billing_service import (
    create_charge, refund_charge_record, cancel_charge_record, VALID_METHODS,
)
from app.utils.operation_log import set_log_context
from app.services.visit_state import has_real_record

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/registration", tags=["挂号"])


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class RegistrationCreate(BaseModel):
    patient_id: int | None = Field(default=None, description="选择已有患者")
    # 复用患者建档 schema，与「患者列表-新增患者」字段完全一致，保证挂号建档信息互通
    new_patient: PatientCreate | None = Field(default=None, description="或在挂号时新建患者")
    department: str | None = Field(default=None, description="科室（建议取自 /registration/options）")
    doctor_id: int | None = Field(default=None, description="接诊医师账号ID（须为启用的医生/管理员账号）")
    registration_fee: float = Field(default=0.0, ge=0, description="挂号费(元)")
    # 开单即收（前台直接收挂号费）
    payment_method: str | None = Field(default=None, description="收款方式")
    paid: float | None = Field(default=None, ge=0, description="实收金额(默认=挂号费)")
    force: bool = Field(default=False, description="该患者今日已挂号时，前台确认后强制再挂")


class RegistrationUpdate(BaseModel):
    status: str | None = Field(default=None, description="就诊状态: 待诊/已接诊/已完成/已取消")
    department: str | None = Field(default=None, description="科室/接诊医师")


class RevertRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200, description="撤销原因（必填，写审计日志）")


def _visit_evidence(db: Session, v: Visit) -> dict:
    """汇总该就诊的**业务事实**，作为状态判定依据（而非凭一次按钮点击）。

    - has_record：主诉已脱离挂号占位符，且至少有一项四诊/诊断/治法/医嘱
    - prescription_count / unsettled：该就诊下有效处方数及未收款数
    - dispensed / paid：是否已发药、是否已有处方收款
    """
    has_record = has_real_record(v)

    rxs = (
        db.query(Prescription)
        .filter(Prescription.visit_id == v.id, Prescription.status != "已取消")
        .all()
    )
    active_charges: dict[int, str] = {}
    if rxs:
        for c in db.query(Charge).filter(
            Charge.prescription_id.in_([r.id for r in rxs]),
            Charge.kind == "prescription",
            Charge.status.in_(("待收费", "已收费")),
        ).all():
            active_charges[c.prescription_id] = c.status
    unsettled = sum(
        1 for r in rxs
        if active_charges.get(r.id) != "已收费"
    )
    return {
        "has_record": has_record,
        "prescription_count": len(rxs),
        "unsettled_prescriptions": unsettled,
        "dispensed": any(r.status == "已发药" for r in rxs),
        "paid_prescriptions": sum(1 for s in active_charges.values() if s == "已收费"),
    }


def _completion_blockers(ev: dict) -> list[str]:
    """「完成就诊」的硬性前置条件：必须留下真实的本次诊疗记录。"""
    if not ev["has_record"]:
        return ["尚未填写本次就诊病历（主诉 + 四诊/诊断/治法/医嘱任一）"]
    return []


def _completion_warnings(ev: dict) -> list[str]:
    """不阻断业务的提醒：钱和药还没走完，但医生确实看完了。"""
    warns = []
    if ev["unsettled_prescriptions"]:
        warns.append(f"有 {ev['unsettled_prescriptions']} 张处方尚未收款，完成后请引导患者缴费")
    if ev["prescription_count"] and not ev["dispensed"]:
        warns.append("处方尚未发药")
    return warns


def _can_revert(v: Visit, ev: dict) -> tuple[bool, str]:
    """受控撤销：只在「钱和药都没动、也没写病历」时允许回退，避免把已完成状态当儿戏。"""
    if v.status == "已接诊":
        if ev["has_record"] or ev["prescription_count"]:
            return False, "该就诊已写入病历或开方，不可撤回「待诊」"
        return True, "叫号误操作，撤回「待诊」"
    if v.status == "已完成":
        if ev["dispensed"] or ev["paid_prescriptions"]:
            return False, "已有处方发药或收款，不可撤销「已完成」（如需更正请走作废/退费流程）"
        return True, "撤销「已完成」，回到「已接诊」"
    return False, f"当前状态「{v.status}」不可撤销"


def _doctor_names(db: Session, visits: list[Visit]) -> dict[int, str]:
    """批量取接诊医师显示名，避免队列 N+1。"""
    ids = {v.doctor_id for v in visits if v.doctor_id}
    if not ids:
        return {}
    return {
        u.id: (u.display_name or u.username)
        for u in db.query(User).filter(User.id.in_(ids)).all()
    }


def _appointable(u: User) -> bool:
    """可接诊账号：启用，且角色为医生/管理员（含超级管理员）。"""
    return bool(u.is_active and (u.is_admin or u.role in ("doctor", "admin")))


def _serialize_visit(v: Visit, patient_name: str | None, doctor_name: str | None = None) -> dict:
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
        "doctor_id": v.doctor_id,
        "doctor_name": doctor_name,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _next_queue_no(db: Session, day: str) -> int:
    row = (
        db.query(func.max(Visit.queue_no))
        .filter(
            Visit.registered_at.isnot(None),
            Visit.registered_at >= day + " 00:00:00",
            Visit.registered_at <= day + " 23:59:59.999999",
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
    # 接诊医师必须来自账号管理中的启用医生/管理员账号，杜绝手写姓名与已停用账号
    doctor = None
    if payload.doctor_id is not None:
        doctor = db.query(User).filter(User.id == payload.doctor_id).first()
        if not doctor or not _appointable(doctor):
            raise HTTPException(status_code=400, detail="指定的接诊医师不存在、已停用或不是医生账号")
    # 选了医师就以其所属科室为准，保证科室与账号管理始终一致
    department = (doctor.department if doctor and doctor.department else payload.department)

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
                patient = db.query(Patient).filter(
                    Patient.id == payload.patient_id, Patient.deleted_at.is_(None)
                ).first()
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
                department=department,
                doctor_id=payload.doctor_id,
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
                    note=f"挂号费（{department or '门诊'}）",
                    payment_method=payload.payment_method,
                    paid=payload.paid if payload.paid is not None else payload.registration_fee,
                )
                charge = create_charge(db, cc, current_user, commit=False)

            db.commit()
            db.refresh(visit)
            if charge is not None:
                db.refresh(charge)
            return {
                "visit": _serialize_visit(visit, patient.name,
                                          (doctor.display_name or doctor.username) if doctor else None),
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
            Visit.registered_at <= day + " 23:59:59.999999",
        )
    )
    if status:
        q = q.filter(Visit.status == status)
    rows = q.order_by(Visit.queue_no.asc()).all()

    doctor_names = _doctor_names(db, [v for v, _ in rows])
    items = []
    for v, pname in rows:
        d = _serialize_visit(v, pname, doctor_names.get(v.doctor_id))
        ch = (
            db.query(Charge)
            .filter(Charge.visit_id == v.id, Charge.kind == "registration")
            .order_by(Charge.id.desc())
            .first()
        )
        d["registration_charge"] = ChargeResponse.model_validate(ch).model_dump() if ch else None
        ev = _visit_evidence(db, v)
        d["evidence"] = {
            **ev,
            "can_complete": not _completion_blockers(ev) and v.status == "已接诊",
            "completion_blockers": _completion_blockers(ev),
            "completion_warnings": _completion_warnings(ev),
            "can_revert": _can_revert(v, ev)[0],
            "revert_hint": _can_revert(v, ev)[1],
        }
        items.append(d)
    return {"items": items, "date": day}


@router.get("/options", summary="挂号可选科室与接诊医师（由启用账号派生）")
def registration_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """科室不另建字典：直接由「启用的医生/管理员账号」的 department 去重派生，
    保证科室与医师永远来自账号管理，不会出现字典里有科室却没医生、或停用账号仍可挂号。

    单独提供此接口而非复用 /auth/users：挂号员通常只有 patient:read/write，
    没有 user:read；也不应把账号权限等敏感信息暴露给前台。
    """
    if not has_perm(current_user, "patient:read"):
        raise HTTPException(status_code=403, detail="无权查看挂号选项")
    users = db.query(User).filter(User.is_active.is_(True)).order_by(User.id).all()
    appointable = [u for u in users if _appointable(u)]
    # 排班启用（排班表已有数据）时，仅展示当日出诊医师；否则保持原行为（全部可接诊医师），
    # 避免引入排班后反而把「未排班日」的挂号卡死——旧库无排班数据时完全无感。
    schedule_enabled = db.query(Schedule).count() > 0
    if schedule_enabled:
        today = date.today()
        on_duty = {row.doctor_id for row in
                   db.query(Schedule.doctor_id).filter(Schedule.schedule_date == today).all()}
        appointable = [u for u in appointable if u.id in on_duty]
    departments = sorted({u.department.strip() for u in appointable
                          if u.department and u.department.strip()})
    doctors = [
        {
            "id": u.id,
            "name": u.display_name or u.username,
            "department": (u.department or "").strip(),
        }
        for u in appointable
    ]
    return {"departments": departments, "doctors": doctors, "schedule_enabled": schedule_enabled}


@router.get("/{visit_id}", summary="挂号/就诊详情（含收费单）")
def visit_detail(visit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not has_perm(current_user, "patient:read"):
        raise HTTPException(status_code=403, detail="无权查看就诊详情")
    v = db.query(Visit).filter(Visit.id == visit_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    pat = db.query(Patient).filter(Patient.id == v.patient_id).first()
    d = _serialize_visit(v, pat.name if pat else None, _doctor_names(db, [v]).get(v.doctor_id))
    charges = db.query(Charge).filter(Charge.visit_id == v.id).all()
    d["charges"] = [ChargeResponse.model_validate(c).model_dump() for c in charges]
    ev = _visit_evidence(db, v)
    d["evidence"] = {
        **ev,
        "can_complete": not _completion_blockers(ev) and v.status == "已接诊",
        "completion_blockers": _completion_blockers(ev),
        "completion_warnings": _completion_warnings(ev),
        "can_revert": _can_revert(v, ev)[0],
        "revert_hint": _can_revert(v, ev)[1],
    }
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
        # 「已完成」必须有业务依据：本次就诊留下真实病历，而不是点一下按钮就算看完
        if payload.status == "已完成" and v.status != "已完成":
            blockers = _completion_blockers(_visit_evidence(db, v))
            if blockers:
                raise HTTPException(
                    status_code=400,
                    detail="无法完成就诊：" + "；".join(blockers) + "。请先在患者详情完善本次就诊记录。",
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
    return _serialize_visit(v, pat.name if pat else None, _doctor_names(db, [v]).get(v.doctor_id))


@router.post("/{visit_id}/call", summary="叫号/接诊（待诊 -> 已接诊）")
def call_visit(visit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return update_registration(visit_id, RegistrationUpdate(status="已接诊"), db, current_user)


@router.post("/{visit_id}/complete", summary="完成就诊（已接诊 -> 已完成）")
def complete_visit(visit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return update_registration(visit_id, RegistrationUpdate(status="已完成"), db, current_user)


@router.post("/{visit_id}/revert", summary="撤销误操作（受控回退 + 写审计日志）")
def revert_visit(
    visit_id: int,
    payload: RevertRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """点错「接诊 / 完成」时的补救通道，但只在业务事实允许时回退：

    - 已接诊 → 待诊：仅限尚未写病历、未开方（纯叫号点错）
    - 已完成 → 已接诊：仅限没有处方发药、没有处方收款（钱和药都没动）
    - 已发药/已收款后不允许回退，只能走「作废 / 退费」重开，避免账实不符
    每次撤销都记录操作人、时间、原因到操作日志。
    """
    if not has_perm(current_user, "patient:write"):
        raise HTTPException(status_code=403, detail="无权变更就诊状态")
    v = db.query(Visit).filter(Visit.id == visit_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="就诊记录不存在")

    ev = _visit_evidence(db, v)
    ok, hint = _can_revert(v, ev)
    if not ok:
        raise HTTPException(status_code=400, detail=hint)

    old_status = v.status
    new_status = "待诊" if old_status == "已接诊" else "已接诊"
    v.status = new_status
    db.commit()
    db.refresh(v)
    pat = db.query(Patient).filter(Patient.id == v.patient_id).first()
    set_log_context(
        request,
        level="WARN",
        action="撤销就诊状态",
        message=f"{pat.name if pat else '患者 #' + str(v.patient_id)}：就诊状态 {old_status} → {new_status}；原因：{payload.reason}",
        target=f"{pat.name if pat else '患者 #' + str(v.patient_id)} · 就诊 #{v.id}",
    )
    return _serialize_visit(v, pat.name if pat else None, _doctor_names(db, [v]).get(v.doctor_id))
