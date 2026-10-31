"""处方管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload

from datetime import datetime as _dt, timedelta

from app.database import get_db
from app.models.prescription import ClassicFormula, Prescription, PrescriptionItem, AcupointPrescription, PrescriptionInjection
from app.models.herb import Herb, HerbInventory
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
    return rows


def _compute_total_price(db: Session, items, doses: int, acupuncture_fee: float | None = None) -> float | None:
    """处方计价 = 中药售价合计 + 针灸费用。

    官方售价优先级：库存该药材售价(sale_price) → 药材参考单价(herb.price)。
    无任何中药单价且无针灸费用时返回 None（前端显示—）。
    """
    fee = float(acupuncture_fee or 0)
    herb_total = 0.0
    has_price = False
    if items:
        herb_ids = [it.herb_id for it in items]
        herbs = {h.id: h for h in db.query(Herb).filter(Herb.id.in_(herb_ids)).all()}
        # 每个药材优先取某条正常库存批次的售价，作为本次处方单价；无售价则回退进价
        price_map: dict[int, float | None] = {}
        for inv in db.query(HerbInventory).filter(
            HerbInventory.herb_id.in_(herb_ids),
            HerbInventory.status == "正常",
        ):
            if inv.herb_id not in price_map:
                if inv.sale_price is not None:
                    price_map[inv.herb_id] = float(inv.sale_price)
                elif inv.unit_price is not None:
                    price_map[inv.herb_id] = float(inv.unit_price)
                else:
                    price_map[inv.herb_id] = None
        for it in items:
            p = price_map.get(it.herb_id)
            if p is None:
                h = herbs.get(it.herb_id)
                if h is not None and h.price is not None:
                    p = float(h.price)
            if p is not None:
                herb_total += p * float(it.dose) * (doses or 1)
                has_price = True
    if not has_price and fee <= 0:
        return None
    return round(herb_total + fee, 2)


@router.post("", response_model=PrescriptionResponse, summary="开具处方")
def create_prescription(data: PrescriptionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """开具处方 — 自动校验剂量"""
    herb_ids = [item.herb_id for item in data.items]

    # 剂量检查 → 超限不拦截提交，改为把提醒写入该药备注
    herbs = db.query(Herb).filter(Herb.id.in_(herb_ids)).all()
    herb_map = {h.id: h for h in herbs}

    # 创建处方
    prescription = Prescription(
        visit_id=data.visit_id,
        patient_id=data.patient_id,
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

    # 自动生成随访提醒：医生指定复诊日期 或 依据疗程天数（就诊日 + 疗程天数）
    fu_due = data.follow_up_date
    if not fu_due and data.treatment_days:
        base = _dt.now().date().isoformat()
        if data.visit_id:
            v = db.query(Visit).filter(Visit.id == data.visit_id).first()
            if v and v.visit_date:
                base = str(v.visit_date)[:10]
        try:
            fu_due = (_dt.fromisoformat(base).date() + timedelta(days=data.treatment_days)).isoformat()
        except Exception:
            fu_due = None
    if fu_due:
        db.add(FollowUpReminder(
            patient_id=data.patient_id,
            due_date=fu_due,
            note=f"处方「{data.formula_name or data.prescription_type}」疗程结束后复诊",
            source_type="prescription",
            source_id=prescription.id,
        ))

    db.commit()
    db.refresh(prescription)
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
    return prescription


@router.put("/{prescription_id}", response_model=PrescriptionResponse, summary="编辑处方(发药前可修改)")
def update_prescription(prescription_id: int, data: PrescriptionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prescription = db.query(Prescription).options(joinedload(Prescription.items), joinedload(Prescription.acupoints), joinedload(Prescription.injections)).filter(
        Prescription.id == prescription_id
    ).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.status in ("已发药", "已取消"):
        raise HTTPException(status_code=400, detail=f"处方状态为'{prescription.status}'，不可修改")

    # 更新处方主信息
    prescription.visit_id = data.visit_id
    prescription.patient_id = data.patient_id
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
    db.delete(prescription)
    db.commit()
    return {"message": "处方已删除"}


@router.put("/{prescription_id}/review", response_model=PrescriptionResponse, summary="审核处方")
def review_prescription(prescription_id: int, reviewer_id: int = 1, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.status != "已开":
        raise HTTPException(status_code=400, detail=f"处方状态为'{prescription.status}'，不可审核")
    prescription.status = "已审核"
    prescription.reviewed_by = reviewer_id
    db.commit()
    db.refresh(prescription)
    return prescription


@router.put("/{prescription_id}/dispense", response_model=PrescriptionResponse, summary="发药(扣减库存)")
def dispense_prescription(prescription_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发药：扣减库存，更新处方状态"""
    from app.models.herb import HerbInventory, InventoryTransaction
    from app.database import inventory_lock

    prescription = db.query(Prescription).options(joinedload(Prescription.items), joinedload(Prescription.acupoints)).filter(
        Prescription.id == prescription_id
    ).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.status != "已审核":
        raise HTTPException(status_code=400, detail="处方未审核，不可发药")

    # 扣减库存（进程内锁 + 行锁，避免并发超卖）
    with inventory_lock:
        for item in prescription.items:
            total_qty = float(item.dose) * prescription.doses
            available = db.query(HerbInventory).filter(
                HerbInventory.herb_id == item.herb_id,
                HerbInventory.status == "正常",
            ).with_for_update().all()
            avail_total = sum(float(inv.quantity) for inv in available)

            if avail_total < total_qty:
                raise HTTPException(
                    status_code=400,
                    detail=f"库存不足: {item.herb_name} 需{total_qty}g，可用{avail_total}g",
                )

            remaining = total_qty
            for inv in available:
                if remaining <= 0:
                    break
                deduct = min(float(inv.quantity), remaining)
                inv.quantity = float(inv.quantity) - deduct
                remaining -= deduct

            # 记录出库
            txn = InventoryTransaction(
                herb_id=item.herb_id,
                transaction_type="出库",
                quantity=total_qty,
                before_quantity=avail_total,
                after_quantity=avail_total - total_qty,
                reference_id=prescription.id,
                note=f"处方#{prescription.id}发药",
            )
            db.add(txn)

        prescription.total_price = _compute_total_price(db, prescription.items, prescription.doses, prescription.acupuncture_fee)
        prescription.status = "已发药"
        db.commit()
    db.refresh(prescription)
    return prescription