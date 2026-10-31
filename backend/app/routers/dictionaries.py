"""数据字典路由 —— 受控词表 CRUD"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dictionaries import DictionaryTerm
from app.models.visit import Visit
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.dictionaries import DictTermCreate, DictTermUpdate, DictTermResponse

router = APIRouter(prefix="/dictionaries", tags=["数据字典"])


@router.get("", response_model=list[DictTermResponse], summary="词条列表")
def list_terms(
    term_type: str | None = Query(None, pattern="^(syndrome|tongue|pulse|tag|herb_tag)$"),
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
def create_term(data: DictTermCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
def update_term(term_id: int, data: DictTermUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    term = db.get(DictionaryTerm, term_id)
    if not term:
        raise HTTPException(status_code=404, detail="词条不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(term, k, v)
    db.commit()
    db.refresh(term)
    return term


@router.delete("/{term_id}", summary="删除词条")
def delete_term(term_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    term = db.get(DictionaryTerm, term_id)
    if not term:
        raise HTTPException(status_code=404, detail="词条不存在")
    # 解除就诊记录对该词条的引用，避免孤儿外键（就诊仍有冗余的明文选项）
    for col in (Visit.tongue_body_term_id, Visit.tongue_coat_term_id, Visit.pulse_term_id, Visit.syndrome_term_id):
        db.query(Visit).filter(col == term_id).update({col: None})
    # 多选脉象列表 pulse_term_ids 同样剔除被删词条 id
    for v in db.query(Visit).filter(Visit.pulse_term_ids.isnot(None)).all():
        ids = v.pulse_term_ids or []
        if term_id in ids:
            remaining = [i for i in ids if i != term_id]
            v.pulse_term_ids = remaining if remaining else None
    db.delete(term)
    db.commit()
    return {"detail": "已删除"}