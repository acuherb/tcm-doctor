"""处方管理路由"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.prescription import ClassicFormula, Prescription, PrescriptionItem, AcupointPrescription, PrescriptionInjection
from app.models.herb import IncompatibilityRule, Herb
from app.models.patient import Patient
from app.schemas.prescription import (
    PrescriptionCreate, PrescriptionResponse, PrescriptionItemResponse,
    ClassicFormulaResponse, ClassicFormulaCreate,
)

router = APIRouter(prefix="/prescriptions", tags=["处方管理"])


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
def create_classic_formula(data: ClassicFormulaCreate, db: Session = Depends(get_db)):
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
def import_classic_formulas(data: list[ClassicFormulaCreate] = Body(...), db: Session = Depends(get_db)):
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
def export_classic_formulas(db: Session = Depends(get_db)):
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
def update_classic_formula(formula_id: int, data: ClassicFormulaCreate, db: Session = Depends(get_db)):
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
def delete_classic_formula(formula_id: int, db: Session = Depends(get_db)):
    formula = db.query(ClassicFormula).filter(ClassicFormula.id == formula_id).first()
    if not formula:
        raise HTTPException(status_code=404, detail="方剂不存在")
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


@router.post("", response_model=PrescriptionResponse, summary="开具处方")
def create_prescription(data: PrescriptionCreate, db: Session = Depends(get_db)):
    """开具处方 — 自动校验配伍禁忌和剂量"""
    herb_ids = [item.herb_id for item in data.items]

    # 配伍禁忌检查
    conflicts = db.query(IncompatibilityRule).filter(
        (IncompatibilityRule.herb_a_id.in_(herb_ids)) & (IncompatibilityRule.herb_b_id.in_(herb_ids))
    ).all()

    if conflicts:
        herbs = db.query(Herb).filter(Herb.id.in_(herb_ids)).all()
        herb_map = {h.id: h.name for h in herbs}
        conflict_names = [
            f"{herb_map.get(c.herb_a_id, '?')} + {herb_map.get(c.herb_b_id, '?')} ({c.rule_type})"
            for c in conflicts
        ]
        raise HTTPException(
            status_code=400,
            detail=f"配伍禁忌冲突: {', '.join(conflict_names)}",
        )

    # 剂量检查
    herbs = db.query(Herb).filter(Herb.id.in_(herb_ids)).all()
    herb_map = {h.id: h for h in herbs}
    for item in data.items:
        herb = herb_map.get(item.herb_id)
        if herb and herb.dosage_max and item.dose > float(herb.dosage_max):
            raise HTTPException(
                status_code=400,
                detail=f"剂量超限: {herb.name} 最大剂量{herb.dosage_max}g，实际{item.dose}g",
            )

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
    )
    db.add(prescription)
    db.flush()

    # 创建药味明细
    for item_data in data.items:
        item = PrescriptionItem(
            prescription_id=prescription.id,
            herb_id=item_data.herb_id,
            herb_name=item_data.herb_name,
            dose=item_data.dose,
            special_method=item_data.special_method,
            is_king_herb=item_data.is_king_herb,
            note=item_data.note,
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
def update_prescription(prescription_id: int, data: PrescriptionCreate, db: Session = Depends(get_db)):
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

    # 重建药味 / 配穴 / 针剂明细
    prescription.items = [
        PrescriptionItem(
            herb_id=i.herb_id, herb_name=i.herb_name, dose=i.dose,
            special_method=i.special_method, is_king_herb=i.is_king_herb, note=i.note,
        ) for i in data.items
    ]
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

    db.commit()
    db.refresh(prescription)
    if prescription.patient_id:
        patient = db.query(Patient).filter(Patient.id == prescription.patient_id).first()
        if patient:
            prescription.patient_name = patient.name
    return prescription


@router.delete("/{prescription_id}", summary="删除处方(发药前可删除)")
def delete_prescription(prescription_id: int, db: Session = Depends(get_db)):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.status in ("已发药", "已取消"):
        raise HTTPException(status_code=400, detail=f"处方状态为'{prescription.status}'，不可删除")
    db.delete(prescription)
    db.commit()
    return {"message": "处方已删除"}


@router.put("/{prescription_id}/review", response_model=PrescriptionResponse, summary="审核处方")
def review_prescription(prescription_id: int, reviewer_id: int = 1, db: Session = Depends(get_db)):
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
def dispense_prescription(prescription_id: int, db: Session = Depends(get_db)):
    """发药：扣减库存，更新处方状态"""
    from app.models.herb import HerbInventory, InventoryTransaction

    prescription = db.query(Prescription).options(joinedload(Prescription.items), joinedload(Prescription.acupoints)).filter(
        Prescription.id == prescription_id
    ).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="处方不存在")
    if prescription.status != "已审核":
        raise HTTPException(status_code=400, detail="处方未审核，不可发药")

    # 扣减库存
    for item in prescription.items:
        total_qty = float(item.dose) * prescription.doses
        available = db.query(HerbInventory).filter(
            HerbInventory.herb_id == item.herb_id,
            HerbInventory.status == "正常",
        ).all()
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

    prescription.status = "已发药"
    db.commit()
    db.refresh(prescription)
    return prescription