"""腧穴字典路由"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.acupuncture import Acupoint
from app.schemas.acupuncture import AcupointCreate, AcupointUpdate, AcupointResponse

router = APIRouter(prefix="/acupoints", tags=["针灸"])


@router.get("", response_model=list[AcupointResponse], summary="腧穴列表")
def list_acupoints(
    meridian: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Acupoint)
    if meridian:
        query = query.filter(Acupoint.meridian == meridian)
    if search:
        query = query.filter(Acupoint.name.like(f"%{search}%"))
    return query.order_by(Acupoint.meridian, Acupoint.id).all()


@router.post("", response_model=AcupointResponse, summary="新增腧穴")
def create_acupoint(data: AcupointCreate, db: Session = Depends(get_db)):
    if db.query(Acupoint).filter(Acupoint.name == data.name).first():
        raise HTTPException(status_code=400, detail=f"腧穴「{data.name}」已存在")
    row = Acupoint(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{acupoint_id}", response_model=AcupointResponse, summary="编辑腧穴")
def update_acupoint(acupoint_id: int, data: AcupointUpdate, db: Session = Depends(get_db)):
    row = db.query(Acupoint).filter(Acupoint.id == acupoint_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="腧穴不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{acupoint_id}", summary="删除腧穴")
def delete_acupoint(acupoint_id: int, db: Session = Depends(get_db)):
    row = db.query(Acupoint).filter(Acupoint.id == acupoint_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="腧穴不存在")
    db.delete(row)
    db.commit()
    return {"message": "已删除"}


@router.get("/export", response_model=list[AcupointResponse], summary="导出全量腧穴")
def export_acupoints(db: Session = Depends(get_db)):
    return db.query(Acupoint).order_by(Acupoint.meridian, Acupoint.id).all()


@router.post("/import", response_model=dict, summary="批量导入腧穴(按穴名 upsert)")
def import_acupoints(data: list[AcupointCreate] = Body(...), db: Session = Depends(get_db)):
    imported, updated = 0, 0
    for item in data:
        existing = db.query(Acupoint).filter(Acupoint.name == item.name).first()
        if existing:
            for k, v in item.model_dump().items():
                if v is not None:
                    setattr(existing, k, v)
            updated += 1
        else:
            db.add(Acupoint(**item.model_dump()))
            imported += 1
    db.commit()
    return {"imported": imported, "updated": updated, "total": len(data)}