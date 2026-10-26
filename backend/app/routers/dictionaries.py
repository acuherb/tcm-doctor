"""主数据字典路由 —— 受控词表 CRUD"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dictionaries import DictionaryTerm
from app.schemas.dictionaries import DictTermCreate, DictTermUpdate, DictTermResponse

router = APIRouter(prefix="/dictionaries", tags=["主数据字典"])


@router.get("", response_model=list[DictTermResponse], summary="词条列表")
def list_terms(
    term_type: str | None = Query(None, pattern="^(syndrome|tongue|pulse)$"),
    meridian: str | None = Query(None),
    aspect: str | None = Query(None),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(DictionaryTerm)
    if term_type:
        query = query.filter(DictionaryTerm.term_type == term_type)
    if meridian:
        query = query.filter(DictionaryTerm.meridian == meridian)
    if aspect:
        query = query.filter(DictionaryTerm.aspect == aspect)
    if is_active is not None:
        query = query.filter(DictionaryTerm.is_active == is_active)
    if search:
        query = query.filter(DictionaryTerm.name.contains(search))
    return query.order_by(DictionaryTerm.term_type, DictionaryTerm.name).all()


@router.post("", response_model=DictTermResponse, summary="新增词条")
def create_term(data: DictTermCreate, db: Session = Depends(get_db)):
    existing = db.query(DictionaryTerm).filter(
        DictionaryTerm.term_type == data.term_type, DictionaryTerm.name == data.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"词条'{data.name}'已存在")
    term = DictionaryTerm(**data.model_dump())
    db.add(term)
    db.commit()
    db.refresh(term)
    return term


@router.get("/{term_id}", response_model=DictTermResponse, summary="词条详情")
def get_term(term_id: int, db: Session = Depends(get_db)):
    term = db.get(DictionaryTerm, term_id)
    if not term:
        raise HTTPException(status_code=404, detail="词条不存在")
    return term


@router.put("/{term_id}", response_model=DictTermResponse, summary="更新词条")
def update_term(term_id: int, data: DictTermUpdate, db: Session = Depends(get_db)):
    term = db.get(DictionaryTerm, term_id)
    if not term:
        raise HTTPException(status_code=404, detail="词条不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(term, k, v)
    db.commit()
    db.refresh(term)
    return term


@router.delete("/{term_id}", summary="删除词条")
def delete_term(term_id: int, db: Session = Depends(get_db)):
    term = db.get(DictionaryTerm, term_id)
    if not term:
        raise HTTPException(status_code=404, detail="词条不存在")
    db.delete(term)
    db.commit()
    return {"detail": "已删除"}