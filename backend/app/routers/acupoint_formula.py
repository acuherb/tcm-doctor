"""针灸方库路由"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.acupuncture import AcupointFormula
from app.schemas.acupuncture import (
    AcupointFormulaCreate, AcupointFormulaUpdate, AcupointFormulaResponse,
)

router = APIRouter(prefix="/acupoint-formulas", tags=["针灸方库"])


@router.get("", response_model=list[AcupointFormulaResponse], summary="针灸方列表")
def list_acupoint_formulas(
    source: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(AcupointFormula)
    if source:
        query = query.filter(AcupointFormula.source == source)
    if search:
        query = query.filter(AcupointFormula.name.contains(search))
    return query.order_by(AcupointFormula.source, AcupointFormula.name).all()


@router.post("", response_model=AcupointFormulaResponse, summary="新增针灸方")
def create_acupoint_formula(data: AcupointFormulaCreate, db: Session = Depends(get_db)):
    if db.query(AcupointFormula).filter(AcupointFormula.name == data.name).first():
        raise HTTPException(status_code=400, detail=f"针灸方「{data.name}」已存在")
    formula = AcupointFormula(
        name=data.name,
        aliases=data.aliases or [],
        source=data.source,
        efficacy=data.efficacy,
        indications=data.indications,
        usage=data.usage,
        technique=data.technique,
        treatment_frequency=data.treatment_frequency,
        treatment_days=data.treatment_days,
        composition=data.composition or {"acupoints": []},
        notes=data.notes,
    )
    db.add(formula)
    db.commit()
    db.refresh(formula)
    return formula


@router.post("/import", summary="批量导入针灸方(按方名 upsert)")
def import_acupoint_formulas(data: list[AcupointFormulaCreate] = Body(...), db: Session = Depends(get_db)):
    created, updated = 0, 0
    for d in data:
        existing = db.query(AcupointFormula).filter(AcupointFormula.name == d.name).first()
        if existing:
            existing.aliases = d.aliases or existing.aliases
            existing.source = d.source if d.source is not None else existing.source
            existing.efficacy = d.efficacy if d.efficacy is not None else existing.efficacy
            existing.indications = d.indications if d.indications is not None else existing.indications
            existing.usage = d.usage if d.usage is not None else existing.usage
            existing.technique = d.technique if d.technique is not None else existing.technique
            existing.treatment_frequency = d.treatment_frequency if d.treatment_frequency is not None else existing.treatment_frequency
            existing.treatment_days = d.treatment_days if d.treatment_days is not None else existing.treatment_days
            existing.composition = d.composition if d.composition is not None else existing.composition
            existing.notes = d.notes if d.notes is not None else existing.notes
            updated += 1
        else:
            db.add(AcupointFormula(
                name=d.name, aliases=d.aliases or [], source=d.source,
                efficacy=d.efficacy, indications=d.indications, usage=d.usage,
                technique=d.technique, treatment_frequency=d.treatment_frequency,
                treatment_days=d.treatment_days,
                composition=d.composition or {"acupoints": []}, notes=d.notes,
            ))
            created += 1
    db.commit()
    return {"created": created, "updated": updated, "total": created + updated}


@router.get("/export", summary="导出全部针灸方(JSON)")
def export_acupoint_formulas(db: Session = Depends(get_db)):
    formulas = db.query(AcupointFormula).order_by(AcupointFormula.source, AcupointFormula.name).all()
    return [{
        "name": f.name,
        "aliases": f.aliases or [],
        "source": f.source,
        "efficacy": f.efficacy,
        "indications": f.indications,
        "usage": f.usage,
        "technique": f.technique,
        "treatment_frequency": f.treatment_frequency,
        "treatment_days": f.treatment_days,
        "composition": f.composition,
        "notes": f.notes,
    } for f in formulas]


@router.get("/{formula_id}", response_model=AcupointFormulaResponse, summary="针灸方详情")
def get_acupoint_formula(formula_id: int, db: Session = Depends(get_db)):
    formula = db.query(AcupointFormula).filter(AcupointFormula.id == formula_id).first()
    if not formula:
        raise HTTPException(status_code=404, detail="针灸方不存在")
    return formula


@router.put("/{formula_id}", response_model=AcupointFormulaResponse, summary="编辑针灸方")
def update_acupoint_formula(formula_id: int, data: AcupointFormulaUpdate, db: Session = Depends(get_db)):
    formula = db.query(AcupointFormula).filter(AcupointFormula.id == formula_id).first()
    if not formula:
        raise HTTPException(status_code=404, detail="针灸方不存在")
    formula.name = data.name if data.name is not None else formula.name
    formula.aliases = data.aliases if data.aliases is not None else formula.aliases
    formula.source = data.source if data.source is not None else formula.source
    formula.efficacy = data.efficacy if data.efficacy is not None else formula.efficacy
    formula.indications = data.indications if data.indications is not None else formula.indications
    formula.usage = data.usage if data.usage is not None else formula.usage
    formula.technique = data.technique if data.technique is not None else formula.technique
    formula.treatment_frequency = data.treatment_frequency if data.treatment_frequency is not None else formula.treatment_frequency
    formula.treatment_days = data.treatment_days if data.treatment_days is not None else formula.treatment_days
    formula.composition = data.composition if data.composition is not None else formula.composition
    formula.notes = data.notes if data.notes is not None else formula.notes
    db.commit()
    db.refresh(formula)
    return formula


@router.delete("/{formula_id}", summary="删除针灸方")
def delete_acupoint_formula(formula_id: int, db: Session = Depends(get_db)):
    formula = db.query(AcupointFormula).filter(AcupointFormula.id == formula_id).first()
    if not formula:
        raise HTTPException(status_code=404, detail="针灸方不存在")
    db.delete(formula)
    db.commit()
    return {"deleted": formula_id}
