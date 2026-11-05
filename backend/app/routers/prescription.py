"""处方管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from datetime import datetime as _dt, timedelta

from app.database import get_db
from app.config import settings
from app.models.prescription import (
    ClassicFormula, Prescription, PrescriptionItem, AcupointPrescription, PrescriptionInjection,
    compute_prescription_hash, compute_signature,
)
from app.models.herb import Herb
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.followup_reminder import FollowUpReminder
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.prescription import (
    PrescriptionCreate, PrescriptionResponse, PrescriptionItemResponse,
    ClassicFormulaResponse, ClassicFormulaCreate,
)

router = APIRouter(prefix="/prescriptions", tags=["处方管理"])


def _refresh_dosage_reminder(note: str, herb, dose: float) -> str:
    """根据当前剂量刷新备注中的剂量超限提醒。

    先移除旧的剂量超限提醒片段，再按当前剂量决定是否追加新的，确保提醒与剂量保持一致。
    """
    note = note or ""
    # 移除旧提醒片段
    remains = [s.strip() for s in note.split("；") if s.strip()]
    remains = [s for s in remains if not s.startswith("⚠️ 剂量超限提醒")]
    # 按当前剂量判断是否超限
    if herb and herb.dosage_max and dose > float(herb.dosage_max):
        remind = f"⚠️ 剂量超限提醒：最大剂量{herb.dosage_max}g，实际{dose}g，请核对"
        remains.append(remind)
    return "；".join(remains)


def _derive_followup(data: PrescriptionCreate, db: Session):
    """推算复诊提醒日期（与随访提醒联动）。

    - 医生手动指定 follow_up_date 时优先使用；
    - 否则综合「中药剂数(doses≈天数，默认1剂/日)」与「针灸疗程天数(treatment_days)」，
      取较晚结束者（复诊为单次，应在两个疗程都结束后）；
    - 纯中药仅填剂数、或针灸仅填疗程天数、或两者兼有，均能生成提醒；两者皆无则不生成。
    返回 (due_date, note)，无提醒时均为 None。
    """
    if data.follow_up_date:
        return data.follow_up_date, None
    course_days = 0
    desc: list[str] = []
    if data.items and data.doses:
        course_days = max(course_days, int(data.doses))
        desc.append(f"中药{data.doses}剂")
    if data.treatment_days:
        course_days = max(course_days, int(data.treatment_days))
        desc.append(f"针灸{data.treatment_days}天疗程")
    if course_days <= 0:
        return None, None
    base = _dt.now().date().isoformat()
    if data.visit_id:
        v = db.query(Visit).filter(Visit.id == data.visit_id).first()
        if v and v.visit_date:
            base = str(v.visit_date)[:10]
    try:
        due = (_dt.fromisoformat(base).date() + timedelta(days=course_days)).isoformat()
    except Exception:
        return None, None
    note = f"处方「{data.formula_name or data.prescription_type}」疗程结束复诊"
    if desc:
        note += f"（{', '.join(desc)}）"
    return due, note


# ── 经典方剂库（必须在 /{prescription_id} 之前，否则会被动态路由捕获） ──

@router.get("/classic-formulas", response_model=list[ClassicFormulaResponse], summary="经典方列表")
def list_classic_formulas(
    source: str | None = Query(None, description="出处筛选"),
    search: str | None = Query(None, description="搜索方名"),
    db: Session = Depends(get_db),
):
    query = db.query(ClassicFormula)
    if source:
        query = query.filter(ClassicFormula.source == source)
    if search:
        query = query.filter(ClassicFormula.name.contains(search))
    return query.order_by(ClassicFormula.source, ClassicFormula.name).all()


# ── 六经 → 候选经方（倪师体系） ──
MERIDIAN_FORMULAS: dict[str, list[str]] = {
    "太阳": ["桂枝汤", "麻黄汤", "葛根汤", "桂枝加葛根汤", "小青龙汤"],
    "阳明": ["白虎汤", "大承气汤", "小承气汤", "调胃承气汤", "竹叶石膏汤"],
    "少阳": ["小柴胡汤", "大柴胡汤", "柴胡桂枝汤"],
    "太阴": ["理中汤", "附子理中汤", "四逆汤", "理中丸"],
    "少阴": ["四逆汤", "真武汤", "白通汤", "附子汤", "四逆加人参汤"],
    "厥阴": ["乌梅丸", "当归四逆汤", "吴茱萸汤", "半夏泻心汤"],
}


@router.get("/classic-formulas/recommend", summary="按六经推荐候选经方")
def recommend_formulas(
    meridian: str = Query(..., description="六经：太阳/阳明/少阳/太阴/少阴/厥阴"),
    db: Session = Depends(get_db),
):
    names = MERIDIAN_FORMULAS.get(meridian, [])
    matched = []
    if names:
        matched = db.query(ClassicFormula).filter(ClassicFormula.name.in_(names)).all()
    matched_ids = {m.id for m in matched}
    matched_names = {m.name for m in matched}
    missing = [n for n in names if n not in matched_names]
    return {
        "meridian": meridian,
        "matched": matched,
        "missing": missing,
        "stock": bool(matched_ids),  # 兼容旧调用
    }


@router.post("/classic-formulas", response_model=ClassicFormulaResponse, summary="新增经典方")
def create_classic_formula(data: ClassicFormulaCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    formula = ClassicFormula(
        name=data.name,
        aliases=data.aliases or [],
        source=data.source,
        composition=data.composition or {"herbs": []},
        efficacy=data.efficacy,
        indications=data.indications,
        usage=data.usage,
        modifications=data.modifications,
    )
    db.add(formula)
    db.commit()
    db.refresh(formula)
    return formula


@router.post("/classic-formulas/import", summary="批量导入经典方(按方名 upsert)")
def import_classic_formulas(data: list[ClassicFormulaCreate] = Body(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    created, updated = 0, 0
    for d in data:
        existing = db.query(ClassicFormula).filter(ClassicFormula.name == d.name).first()
        if existing:
            existing.aliases = d.aliases or existing.aliases
            existing.source = d.source or existing.source
            existing.composition = d.composition or existing.composition
            existing.efficacy = d.efficacy if d.efficacy is not None else existing.efficacy
            existing.indications = d.indications if d.indications is not None else existing.indications
            existing.usage = d.usage if d.usage is not None else existing.usage
            existing.modifications = d.modifications if d.modifications is not None else existing.modifications
            updated += 1
        else:
            db.add(ClassicFormula(
                name=d.name, aliases=d.aliases or [], source=d.source,
                composition=d.composition or {"herbs": []},
                efficacy=d.efficacy, indications=d.indications,
                usage=d.usage, modifications=d.modifications,
            ))
            created += 1
    db.commit()
    return {"created": created, "updated": updated, "total": created + updated}


@router.get("/classic-formulas/export", summary="导出全部经典方(JSON)")
def export_classic_formulas(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    formulas = db.query(ClassicFormula).order_by(ClassicFormula.source, ClassicFormula.name).all()
    return [{
        "name": f.name,
        "aliases": f.aliases or [],
        "source": f.source,
        "composition": f.composition,
        "efficacy": f.efficacy,
        "indications": f.indications,
        "usage": f.usage,
        "modifications": f.modifications,
    } for f in formulas]


@router.get("/classic-formulas/{formula_id}", response_model=ClassicFormulaResponse, summary="经典方详情")
def get_classic_formula(formula_id: int, db: Session = Depends(get_db)):
    formula = db.query(ClassicFormula).filter(ClassicFormula.id == formula_id).first()
    if not formula:
        raise HTTPException(status_code=404, detail="方剂不存在")
    return formula


@router.put("/classic-formulas/{formula_id}", response_model=ClassicFormulaResponse, summary="编辑经典方")
def update_classic_formula(formula_id: int, data: ClassicFormulaCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    formula = db.query(ClassicFormula).filter(ClassicFormula.id == formula_id).first()
    if not formula:
        raise HTTPException(status_code=404, detail="方剂不存在")
    formula.name = data.name
    formula.aliases = data.aliases or formula.aliases
    formula.source = data.source if data.source is not None else formula.source
    formula.composition = data.composition if data.composition is not None else formula.composition
    formula.efficacy = data.efficacy if data.efficacy is not None else formula.efficacy
    formula.indications = data.indications if data.indications is not None else formula.indications
    formula.usage = data.usage if data.usage is not None else formula.usage
    formula.modifications = data.modifications if data.modifications is not None else formula.modifications
    db.commit()
    db.refresh(formula)
    return formula


@router.delete("/classic-formulas/{formula_id}", summary="删除经典方")
def delete_classic_formula(formula_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    formula = db.query(ClassicFormula).filter(ClassicFormula.id == formula_id).first()
    if not formula:
        raise HTTPException(status_code=404, detail="方剂不存在")
    # 解除处方对该方的引用，避免孤儿外键（处方仍保留冗余的 formula_name，可正常显示）
    db.query(Prescription).filter(Prescription.classic_formula_id == formula_id).update(
        {Prescription.classic_formula_id: None, Prescription.is_classic: False}
    )
    db.delete(formula)
    db.commit()
    return {"deleted": formula_id}


# ── 处方 CRUD ──

def _doctor_snapshot(user: User) -> tuple[int | None, str | None]:
    """开方医师信息：优先用账号姓名，回退登录名，保证打印有值。"""
    if user is None:
        return None, None
    name = (getattr(user, "display_name", None) or "").strip() or user.username
    return user.id, name


def _active_charges(db: Session, prescription_id: int) -> list:
    """该处方的在账收费单（待收费/已收费）。已退费、已取消为终态历史，不算在账。"""
    from app.models.billing import Charge

    return (
        db.query(Charge)
        .filter(
            Charge.prescription_id == prescription_id,
            Charge.kind == "prescription",
            Charge.status.in_(("待收费", "已收费")),
        )
        .all()
    )


def _settle_prescription_charges(db: Session, prescription_id: int, current_user) -> None:
    """处方作废联动：已收的自动全额退，待收的自动作废，钱不留在账上。

    与「退号联动退挂号费」保持同一口径；处方已取消时路由直接幂等返回，不会重复退。
    """
    from app.services.billing_service import refund_charge_record, cancel_charge_record

    for c in _active_charges(db, prescription_id):
        if c.status == "已收费":
            refund_charge_record(c, None, f"处方 #{prescription_id} 作废联动退费", current_user)
        else:
            cancel_charge_record(c, f"处方 #{prescription_id} 作废联动清待收单", current_user)


def _attach_charge_info(db: Session, rows: list) -> list:
    """批量回填处方的「在账收费单」信息，避免 N+1；前端据此收敛收费按钮。

    已退费/已取消是终态历史，不回填 —— 这类处方可以合法重新开单收费。
    """
    from app.models.billing import Charge

    if not rows:
        return rows
    active = (
        db.query(Charge)
        .filter(
            Charge.prescription_id.in_([r.id for r in rows]),
            Charge.kind == "prescription",
            Charge.status.in_(("待收费", "已收费")),
        )
        .order_by(Charge.id)
        .all()
    )
    by_pid = {c.prescription_id: c for c in active}
    for r in rows:
        c = by_pid.get(r.id)
        r.charge_id = c.id if c else None
        r.charge_no = c.charge_no if c else None
        r.charge_status = c.status if c else None
    return rows


@router.get("", response_model=list[PrescriptionResponse], summary="处方列表")
def list_prescriptions(
    patient_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Prescription).options(joinedload(Prescription.items), joinedload(Prescription.acupoints), joinedload(Prescription.injections))
    if patient_id:
        query = query.filter(Prescription.patient_id == patient_id)
    if status:
        query = query.filter(Prescription.status == status)
    rows = query.order_by(Prescription.created_at.desc()).limit(limit).all()
    pids = {r.patient_id for r in rows if r.patient_id}
    if pids:
        names = {p.id: p.name for p in db.query(Patient).filter(Patient.id.in_(pids)).all()}
        for r in rows:
            r.patient_name = names.get(r.patient_id)
    return _attach_charge_info(db, rows)


def _compute_total_price(db: Session, items, doses: int, acupuncture_fee: float | None = None) -> float | None:
    """处方计价 = 中药售价合计 + 针灸费用。

    售价优先级：处方项上锁定的单价(开方时按所选批次售价确定) → 物品默认售价(stock_item.sell_price) → 药材参考单价(herb.price)。
    无任何中药单价且无针灸费用时返回 None（前端显示—）。
    """
    from app.models.stock import StockItem

    fee = float(acupuncture_fee or 0)
    herb_total = 0.0
    has_price = False
    if items:
        herb_ids = [it.herb_id for it in items]
        herbs = {h.id: h for h in db.query(Herb).filter(Herb.id.in_(herb_ids)).all()}
        stock_map = (
            {si.herb_id: si for si in db.query(StockItem).filter(StockItem.herb_id.in_(herb_ids)).all()}
            if herb_ids else {}
        )
        for it in items:
            # 优先使用处方项上记录的单价（开方时按所选批次售价确定）
            p = getattr(it, "price", None)
            if p is None:
                si = stock_map.get(it.herb_id)
                if si and si.sell_price is not None:
                    p = float(si.sell_price)
                elif (h := herbs.get(it.herb_id)) and h.price is not None:
                    p = float(h.price)
            if p is not None:
                herb_total += float(p) * float(getattr(it, "dose", 0)) * (doses or 1)
                has_price = True
    if not has_price and fee <= 0:
        return None
    return round(herb_total + fee, 2)


@router.post("", response_model=PrescriptionResponse, summary="开具处方")
def create_prescription(data: PrescriptionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """开具处方 — 自动校验剂量"""
    herb_ids = [item.herb_id for item in data.items]

    # 数据完整性：就诊必须属于所选患者，避免处方挂在 A 患者却指向 B 患者的就诊
    visit = db.query(Visit).filter(Visit.id == data.visit_id).first()
    if not visit or visit.patient_id != data.patient_id:
        raise HTTPException(status_code=400, detail="就诊记录不属于该患者，请检查患者与就诊的对应关系")

    # 剂量检查 → 超限不拦截提交，改为把提醒写入该药备注
    herbs = db.query(Herb).filter(Herb.id.in_(herb_ids)).all()
    herb_map = {h.id: h for h in herbs}

    # 创建处方
    doctor_id, doctor_name = _doctor_snapshot(current_user)
    prescription = Prescription(
        visit_id=data.visit_id,
        patient_id=data.patient_id,
        doctor_id=doctor_id,
        doctor_name=doctor_name,
        formula_name=data.formula_name,
        is_classic=data.is_classic,
        classic_formula_id=data.classic_formula_id,
        acupoint_formula_id=data.acupoint_formula_id,
        preparation_method=data.preparation_method,
        administration=data.administration,
        doses=data.doses,
        doctor_notes=data.doctor_notes,
        prescription_type=data.prescription_type,
        acupoint_formula_name=data.acupoint_formula_name,
        acupoint_technique=data.acupoint_technique,
        treatment_frequency=data.treatment_frequency,
        treatment_days=data.treatment_days,
        acupuncture_fee=data.acupuncture_fee,
    )
    db.add(prescription)
    db.flush()

    # 创建药味明细（剂量超限时自动附加提醒到备注）
    for item_data in data.items:
        note = item_data.note or ""
        herb = herb_map.get(item_data.herb_id)
        note = _refresh_dosage_reminder(note, herb, item_data.dose)
        item = PrescriptionItem(
            prescription_id=prescription.id,
            herb_id=item_data.herb_id,
            herb_name=item_data.herb_name,
            dose=item_data.dose,
            special_method=item_data.special_method,
            is_king_herb=item_data.is_king_herb,
            note=note,
            inventory_id=item_data.inventory_id,
            price=item_data.price,
        )
        db.add(item)

    # 创建针灸配穴
    for acp in data.acupoints:
        db.add(AcupointPrescription(
            prescription_id=prescription.id,
            acupoint_id=acp.acupoint_id,
            acupoint_name=acp.acupoint_name,
            technique=acp.technique,
            retention=acp.retention,
            sequence=acp.sequence,
            note=acp.note,
        ))

    # 创建针剂明细
    for inj in data.injections:
        db.add(PrescriptionInjection(
            prescription_id=prescription.id,
            drug_name=inj.drug_name,
            spec=inj.spec,
            dose=inj.dose,
            usage=inj.usage,
            frequency=inj.frequency,
            note=inj.note,
        ))

    prescription.total_price = _compute_total_price(db, data.items, data.doses)

    # 自动生成随访提醒：医生指定复诊日期 或 综合中药剂数/针灸疗程天数推算
    fu_due, fu_note = _derive_followup(data, db)
    if fu_due:
        db.add(FollowUpReminder(
            patient_id=data.patient_id,
            due_date=fu_due,
            note=fu_note or f"处方「{data.formula_name or data.prescription_type}」复诊",
            source_type="prescription",
            source_id=prescription.id,
        ))

    db.commit()
    db.refresh(prescription)
    # 建立内容哈希基线（防篡改）；新建处方默认未签名
    prescription.content_hash = compute_prescription_hash(prescription)
    db.commit()
    return prescription


@router.get("/{prescription_id}", response_model=PrescriptionResponse, summary="处方详情")
def get_prescription(prescription_id: int, db: Session = Depends(get_db)):
    prescription = db.query(Prescription).options(joinedload(Prescription.items), joinedload(Prescription.acupoints), joinedload(Prescription.injections)).filter(
        Prescription.id == prescription_id
    ).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.patient_id:
        patient = db.query(Patient).filter(Patient.id == prescription.patient_id).first()
        if patient:
            prescription.patient_name = patient.name
    return _attach_charge_info(db, [prescription])[0]


@router.put("/{prescription_id}", response_model=PrescriptionResponse, summary="编辑处方(发药前可修改)")
def update_prescription(prescription_id: int, data: PrescriptionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prescription = db.query(Prescription).options(joinedload(Prescription.items), joinedload(Prescription.acupoints), joinedload(Prescription.injections)).filter(
        Prescription.id == prescription_id
    ).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.status in ("已发药", "已取消"):
        raise HTTPException(status_code=400, detail=f"处方状态为'{prescription.status}'，不可修改")

    # 已有在账收费单时冻结金额：收费单是 total_price 的快照，改方不改钱会造成账实不符。
    # 医嘱/诊断/备注等不影响金额的字段仍可修改；要改方请先退费或作废重开。
    if _active_charges(db, prescription.id):
        from app.models.billing import _to_decimal

        new_total = _compute_total_price(db, data.items, data.doses, data.acupuncture_fee)
        if _to_decimal(new_total or 0) != _to_decimal(prescription.total_price or 0):
            raise HTTPException(
                status_code=400,
                detail="该处方已有在账收费单，金额不可修改；请先退费或作废后重开（医嘱/备注仍可修改）",
            )

    # 数据完整性：就诊必须属于所选患者，避免处方挂在 A 患者却指向 B 患者的就诊
    visit = db.query(Visit).filter(Visit.id == data.visit_id).first()
    if not visit or visit.patient_id != data.patient_id:
        raise HTTPException(status_code=400, detail="就诊记录不属于该患者，请检查患者与就诊的对应关系")

    # 更新处方主信息
    prescription.visit_id = data.visit_id
    prescription.patient_id = data.patient_id
    # 仅补填存量处方的医师信息；已记录的医师不被后来的编辑者覆盖（谁开的方就打印谁）
    if not prescription.doctor_name:
        prescription.doctor_id, prescription.doctor_name = _doctor_snapshot(current_user)
    prescription.formula_name = data.formula_name
    prescription.is_classic = data.is_classic
    prescription.classic_formula_id = data.classic_formula_id
    prescription.acupoint_formula_id = data.acupoint_formula_id
    prescription.preparation_method = data.preparation_method
    prescription.administration = data.administration
    prescription.doses = data.doses
    prescription.doctor_notes = data.doctor_notes
    prescription.prescription_type = data.prescription_type
    prescription.acupoint_formula_name = data.acupoint_formula_name
    prescription.acupoint_technique = data.acupoint_technique
    prescription.treatment_frequency = data.treatment_frequency
    prescription.treatment_days = data.treatment_days
    prescription.acupuncture_fee = data.acupuncture_fee

    # 重建药味 / 配穴 / 针剂明细（剂量超限时自动附加提醒到备注，不拦截提交）
    herb_ids = [i.herb_id for i in data.items]
    dose_herbs = db.query(Herb).filter(Herb.id.in_(herb_ids)).all() if herb_ids else []
    dherb_map = {h.id: h for h in dose_herbs}
    rebuilt_items = []
    for i in data.items:
        note = i.note or ""
        herb = dherb_map.get(i.herb_id)
        note = _refresh_dosage_reminder(note, herb, i.dose)
        rebuilt_items.append(PrescriptionItem(
            herb_id=i.herb_id, herb_name=i.herb_name, dose=i.dose,
            special_method=i.special_method, is_king_herb=i.is_king_herb, note=note,
            inventory_id=i.inventory_id, price=i.price,
        ))
    prescription.items = rebuilt_items
    prescription.acupoints = [
        AcupointPrescription(
            acupoint_id=a.acupoint_id, acupoint_name=a.acupoint_name,
            technique=a.technique, retention=a.retention, sequence=a.sequence, note=a.note,
        ) for a in data.acupoints
    ]
    prescription.injections = [
        PrescriptionInjection(
            drug_name=j.drug_name, spec=j.spec, dose=j.dose,
            usage=j.usage, frequency=j.frequency, note=j.note,
        ) for j in data.injections
    ]

    prescription.total_price = _compute_total_price(db, data.items, data.doses, data.acupuncture_fee)

    # 重建该处方自动生成的随访提醒（编辑后按最新疗程重算复诊日期，避免与实际不符）
    db.query(FollowUpReminder).filter(
        FollowUpReminder.source_type == "prescription",
        FollowUpReminder.source_id == prescription.id,
    ).delete(synchronize_session=False)
    fu_due, fu_note = _derive_followup(data, db)
    if fu_due:
        db.add(FollowUpReminder(
            patient_id=data.patient_id,
            due_date=fu_due,
            note=fu_note or f"处方「{data.formula_name or data.prescription_type}」复诊",
            source_type="prescription",
            source_id=prescription.id,
        ))

    # 内容变动：重算哈希基线，并使既有电子签名失效（编辑后须重新签名）
    prescription.content_hash = compute_prescription_hash(prescription)
    prescription.signed_by = None
    prescription.signed_by_id = None
    prescription.signed_at = None
    prescription.signature = None

    db.commit()
    db.refresh(prescription)
    if prescription.patient_id:
        patient = db.query(Patient).filter(Patient.id == prescription.patient_id).first()
        if patient:
            prescription.patient_name = patient.name
    return prescription


@router.delete("/{prescription_id}", summary="删除处方(发药前可删除)")
def delete_prescription(prescription_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.status in ("已发药", "已取消"):
        raise HTTPException(status_code=400, detail=f"处方状态为'{prescription.status}'，不可删除")
    # 已收费处方不可物理删除：删除不可逆，且会让收费单失去处方快照。
    # 引导走「作废」（自动退费、保留完整审计链）；仅有待收费单则自动作废该单。
    from app.services.billing_service import cancel_charge_record

    active = _active_charges(db, prescription.id)
    if any(c.status == "已收费" for c in active):
        raise HTTPException(status_code=400, detail="该处方已收费，请先「作废」（自动退费）后再删除")
    for c in active:
        cancel_charge_record(c, f"处方 #{prescription.id} 删除联动清待收单", current_user)
    # 级联清理该处方自动生成的随访提醒，避免工作台出现指向已删处方的死链
    db.query(FollowUpReminder).filter(
        FollowUpReminder.source_type == "prescription",
        FollowUpReminder.source_id == prescription.id,
    ).delete(synchronize_session=False)
    # 防御性清理（C）：若该处方（仅可为未发药状态）仍关联任何库存流水，置空其引用，避免孤儿引用
    from app.models.stock import StockTransaction
    db.query(StockTransaction).filter(
        StockTransaction.reference_type == "处方",
        StockTransaction.reference_id == prescription.id,
    ).update({StockTransaction.reference_id: None}, synchronize_session=False)
    db.delete(prescription)
    db.commit()
    return {"message": "处方已删除"}


@router.post("/{prescription_id}/void", response_model=PrescriptionResponse, summary="作废处方（冲红，可退回库存）")
def void_prescription(
    prescription_id: int,
    return_stock: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """作废 / 冲红处方。

    - 已开 / 已审核：仅置为『已取消』，未扣库存，无副作用。
    - 已发药：置为『已取消』；若 return_stock=True（默认），按发药出库流水把库存退回对应批次，
      并生成『冲红』流水，使采购成本 / COGS / 收入在报表中净额抵消（见 stock.py 报表聚合）。
    - 已取消：幂等返回，不重复处理。
    """
    from app.models.stock import StockItem, StockBatch, StockTransaction

    prescription = db.query(Prescription).options(joinedload(Prescription.items)).filter(
        Prescription.id == prescription_id
    ).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.status == "已取消":
        return prescription

    if prescription.status == "已发药" and return_stock:
        # 按发药出库流水回补库存并生成冲红流水
        outflows = (
            db.query(StockTransaction)
            .filter(
                StockTransaction.reference_type == "处方",
                StockTransaction.reference_id == prescription.id,
                StockTransaction.transaction_type == "出库",
            )
            .all()
        )
        for t in outflows:
            qty = float(t.quantity)
            if t.batch_id is not None:
                batch = db.query(StockBatch).filter(StockBatch.id == t.batch_id).with_for_update().first()
                if batch:
                    batch.quantity = float(batch.quantity) + qty
                    if float(batch.quantity) > 0 and batch.status == "停用":
                        batch.status = "正常"
            db.add(StockTransaction(
                item_id=t.item_id, batch_id=t.batch_id, transaction_type="冲红",
                quantity=qty, before_quantity=None, after_quantity=None,
                unit_cost=t.unit_cost, unit_price=t.unit_price,
                cost_amount=(qty * float(t.unit_cost)) if t.unit_cost is not None else None,
                revenue_amount=(-qty * float(t.unit_price)) if t.unit_price is not None else 0.0,
                reference_id=prescription.id, reference_type="处方", operator=current_user.username,
                note=f"处方#{prescription.id}作废冲红(退回批次#{t.batch_id})",
            ))

    # 作废联动退费 / 清待收单：已收的钱自动全额退，避免「方废了钱还挂在账上」
    _settle_prescription_charges(db, prescription.id, current_user)
    prescription.status = "已取消"
    db.commit()
    db.refresh(prescription)
    return prescription


@router.put("/{prescription_id}/review", response_model=PrescriptionResponse, summary="审核处方")
def review_prescription(prescription_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.status != "已开":
        raise HTTPException(status_code=400, detail=f"处方状态为'{prescription.status}'，不可审核")
    prescription.status = "已审核"
    prescription.reviewed_by = current_user.id
    db.commit()
    db.refresh(prescription)
    return prescription


@router.put("/{prescription_id}/dispense", response_model=PrescriptionResponse, summary="发药(扣减库存)")
def dispense_prescription(prescription_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发药：扣减库存（统一 stock 表），更新处方状态。
    单位跟随物品(stock_item.unit)，中药为 g，耗材可为盒/支等。"""
    from app.models.stock import StockItem, StockBatch, StockTransaction
    from app.database import inventory_lock

    prescription = db.query(Prescription).options(joinedload(Prescription.items), joinedload(Prescription.acupoints)).filter(
        Prescription.id == prescription_id
    ).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")

    # 扣减库存（进程内锁 + 行锁，避免并发超卖）。
    with inventory_lock:
        fresh = (
            db.query(Prescription)
            .options(joinedload(Prescription.items))
            .filter(Prescription.id == prescription_id)
            .with_for_update()
            .first()
        )
        if not fresh:
            raise HTTPException(status_code=404, detail="处方不存在")
        if fresh.status != "已审核":
            raise HTTPException(status_code=400, detail="处方未审核或已发药，不可重复发药")

        for item in fresh.items:
            total_qty = float(item.dose) * fresh.doses
            # 该药材对应的库存物品(中药)
            stock_item = db.query(StockItem).filter(StockItem.herb_id == item.herb_id).first()
            if not stock_item:
                raise HTTPException(status_code=400, detail=f"未找到'{item.herb_name}'对应的库存物品")
            item_id = stock_item.id
            unit = stock_item.unit
            sell = float(stock_item.sell_price) if stock_item.sell_price is not None else None
            if item.inventory_id:
                # 按开方所选批次出货；所选批次不足时自动从其它可用批次补差（跨批次拆单）
                inv = db.query(StockBatch).filter(StockBatch.id == item.inventory_id).with_for_update().first()
                if not inv or inv.item_id != item_id:
                    raise HTTPException(status_code=400, detail=f"所选批次不存在: {item.herb_name}")
                avail = float(inv.quantity)
                if avail >= total_qty:
                    before = avail
                    inv.quantity = before - total_qty
                    if float(inv.quantity) <= 0:
                        inv.quantity = 0.0
                        inv.status = "停用"
                    uc_i = float(inv.unit_price) if inv.unit_price is not None else None
                    db.add(StockTransaction(
                        item_id=item_id, batch_id=inv.id, transaction_type="出库", quantity=total_qty,
                        before_quantity=before, after_quantity=float(inv.quantity),
                        unit_cost=uc_i, unit_price=sell,
                        cost_amount=(-total_qty * uc_i) if uc_i is not None else None,
                        revenue_amount=(total_qty * sell) if sell is not None else 0.0,
                        reference_id=fresh.id, reference_type="处方", operator=current_user.username,
                        note=f"处方#{fresh.id}发药(批次#{inv.id})",
                    ))
                else:
                    remaining = total_qty
                    d0 = min(avail, remaining)
                    inv.quantity = avail - d0
                    if float(inv.quantity) <= 0:
                        inv.quantity = 0.0
                        inv.status = "停用"
                    remaining -= d0
                    uc_i = float(inv.unit_price) if inv.unit_price is not None else None
                    db.add(StockTransaction(
                        item_id=item_id, batch_id=inv.id, transaction_type="出库", quantity=d0,
                        before_quantity=avail, after_quantity=float(inv.quantity),
                        unit_cost=uc_i, unit_price=sell,
                        cost_amount=(-d0 * uc_i) if uc_i is not None else None,
                        revenue_amount=(d0 * sell) if sell is not None else 0.0,
                        reference_id=fresh.id, reference_type="处方", operator=current_user.username,
                        note=f"处方#{fresh.id}发药(批次#{inv.id})",
                    ))
                    others = db.query(StockBatch).filter(
                        StockBatch.item_id == item_id,
                        StockBatch.status.in_(["正常", "近效期"]),
                        StockBatch.id != item.inventory_id,
                    ).order_by(
                        func.coalesce(StockBatch.expiry_date, "9999-12-31"), StockBatch.id
                    ).with_for_update().all()
                    for o in others:
                        if remaining <= 0:
                            break
                        od = min(float(o.quantity), remaining)
                        o_before = float(o.quantity)
                        o.quantity = o_before - od
                        if float(o.quantity) <= 0:
                            o.quantity = 0.0
                            o.status = "停用"
                        remaining -= od
                        uc_o = float(o.unit_price) if o.unit_price is not None else None
                        db.add(StockTransaction(
                            item_id=item_id, batch_id=o.id, transaction_type="出库", quantity=od,
                            before_quantity=o_before, after_quantity=float(o.quantity),
                            unit_cost=uc_o, unit_price=sell,
                            cost_amount=(-od * uc_o) if uc_o is not None else None,
                            revenue_amount=(od * sell) if sell is not None else 0.0,
                            reference_id=fresh.id, reference_type="处方", operator=current_user.username,
                            note=f"处方#{fresh.id}发药补差(批次#{o.id})",
                        ))
                    if remaining > 0:
                        raise HTTPException(
                            status_code=400,
                            detail=f"库存不足: {item.herb_name} 共需{total_qty}{unit}，所选批次及可用批次合计仍缺{remaining}{unit}",
                        )
            else:
                # 兼容旧处方（未选批次）：FIFO 全局扣减
                available = db.query(StockBatch).filter(
                    StockBatch.item_id == item_id,
                    StockBatch.status.in_(["正常", "近效期"]),
                ).order_by(
                    func.coalesce(StockBatch.expiry_date, "9999-12-31"), StockBatch.id
                ).with_for_update().all()
                avail_total = sum(float(b.quantity) for b in available)
                if avail_total < total_qty:
                    raise HTTPException(
                        status_code=400,
                        detail=f"库存不足: {item.herb_name} 需{total_qty}{unit}，可用{avail_total}{unit}",
                    )
                remaining = total_qty
                for b in available:
                    if remaining <= 0:
                        break
                    deduct = min(float(b.quantity), remaining)
                    b.quantity = float(b.quantity) - deduct
                    if float(b.quantity) <= 0:
                        b.quantity = 0.0
                        b.status = "停用"
                    remaining -= deduct
                db.add(StockTransaction(
                    item_id=item_id, batch_id=None, transaction_type="出库", quantity=total_qty,
                    before_quantity=avail_total, after_quantity=avail_total - total_qty,
                    unit_cost=None, unit_price=sell,
                    cost_amount=None,
                    revenue_amount=(total_qty * sell) if sell is not None else 0.0,
                    reference_id=fresh.id, reference_type="处方", operator=current_user.username,
                    note=f"处方#{fresh.id}发药",
                ))

        fresh.total_price = _compute_total_price(db, fresh.items, fresh.doses, fresh.acupuncture_fee)
        fresh.status = "已发药"
        db.commit()
    db.refresh(prescription)
    return prescription


# ── 电子签名与防篡改校验 ──

@router.post("/{prescription_id}/sign", response_model=PrescriptionResponse, summary="电子签名(防篡改留痕)")
def sign_prescription(
    prescription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """主治医师对处方进行电子签名：绑定内容哈希 + 签名人 + 时间，生成签名令牌。

    - 已取消的处方不可签名；内容若已被篡改（基线不一致）拒绝签名，须先核对。
    - 签名后若处方内容被改动，令牌将失效（verify 时 signature_valid=False），需重新签名。
    """
    prescription = db.query(Prescription).options(
        joinedload(Prescription.items), joinedload(Prescription.acupoints), joinedload(Prescription.injections)
    ).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.status == "已取消":
        raise HTTPException(status_code=400, detail="已取消的处方不可签名")
    if prescription.tampered:
        raise HTTPException(status_code=400, detail="处方内容已被篡改，无法签名，请核对原始记录")

    doctor_id, doctor_name = _doctor_snapshot(current_user)
    # 以当前内容刷新基线，确保签名锁定的是此刻真实内容
    prescription.content_hash = compute_prescription_hash(prescription)
    prescription.signed_by = doctor_name
    prescription.signed_by_id = doctor_id
    prescription.signed_at = _dt.now()
    prescription.signature = compute_signature(
        prescription.content_hash, doctor_name, prescription.signed_at.isoformat(), settings.signing_secret
    )
    db.commit()
    db.refresh(prescription)
    return prescription


@router.get("/{prescription_id}/verify", summary="校验处方完整性与电子签名")
def verify_prescription(prescription_id: int, db: Session = Depends(get_db)):
    """校验：内容是否被篡改、是否已签名、签名是否有效。

    返回基线哈希与实时重算哈希，便于前端展示「内容未被改动」或「已被篡改」告警。
    """
    prescription = db.query(Prescription).options(
        joinedload(Prescription.items), joinedload(Prescription.acupoints), joinedload(Prescription.injections)
    ).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    return {
        "id": prescription.id,
        "tampered": prescription.tampered,
        "signed": prescription.signed,
        "signature_valid": prescription.signature_valid,
        "stored_hash": prescription.content_hash,
        "computed_hash": prescription.content_hash_current,
        "signed_by": prescription.signed_by,
        "signed_at": prescription.signed_at,
    }