from datetime import date
from math import ceil
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload
from .database import get_db
from .models import Category, Transaction, User
from .schemas import TransactionCreate, TransactionPage, TransactionRead
from .security import current_user

router = APIRouter(prefix='/api/transactions', tags=['Transactions'])

def validate_category(db: Session, category_id: int, direction: str):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(422, 'Choose a valid category')
    if category.type != direction:
        raise HTTPException(422, 'Category must match the income or expense type')
    return category

def owned_transaction(db: Session, user_id: int, transaction_id: int):
    record = db.scalar(select(Transaction).options(joinedload(Transaction.category)).where(Transaction.id == transaction_id, Transaction.user_id == user_id))
    if record is None:
        raise HTTPException(404, 'Transaction not found')
    return record

@router.get('', response_model=TransactionPage)
def list_transactions(
    user: User = Depends(current_user), db: Session = Depends(get_db),
    search: str = Query(default='', max_length=200), category_id: int | None = Query(default=None, gt=0),
    date_from: date | None = None, date_to: date | None = None,
    transaction_type: Literal['income', 'expense'] | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=100),
    sort_by: Literal['transaction_date', 'amount', 'merchant', 'description', 'category', 'transaction_type', 'created_at'] = 'transaction_date',
    sort_order: Literal['asc', 'desc'] = 'desc',
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, 'Start date must be on or before end date')
    conditions = [Transaction.user_id == user.id]
    if search.strip():
        conditions.append(or_(Transaction.description.icontains(search.strip(), autoescape=True), Transaction.merchant.icontains(search.strip(), autoescape=True)))
    if category_id:
        conditions.append(Transaction.category_id == category_id)
    if date_from:
        conditions.append(Transaction.transaction_date >= date_from)
    if date_to:
        conditions.append(Transaction.transaction_date <= date_to)
    if transaction_type:
        conditions.append(Transaction.transaction_type == transaction_type)
    total = db.scalar(select(func.count(Transaction.id)).where(*conditions))
    sort_column = Category.name if sort_by == 'category' else getattr(Transaction, sort_by)
    order = sort_column.asc().nulls_last() if sort_order == 'asc' else sort_column.desc().nulls_last()
    records = db.scalars(select(Transaction).join(Category).options(joinedload(Transaction.category)).where(*conditions).order_by(order, Transaction.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return TransactionPage(items=records, total=total, page=page, page_size=page_size, pages=ceil(total / page_size))

@router.post('', response_model=TransactionRead, status_code=201)
def add_transaction(body: TransactionCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    validate_category(db, body.category_id, body.transaction_type)
    record = Transaction(**body.model_dump(exclude={'source'}), source='manual', user_id=user.id)
    db.add(record)
    db.commit()
    return owned_transaction(db, user.id, record.id)

@router.get('/{transaction_id}', response_model=TransactionRead)
def transaction_details(transaction_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return owned_transaction(db, user.id, transaction_id)

@router.put('/{transaction_id}', response_model=TransactionRead)
def edit_transaction(transaction_id: int, body: TransactionCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    record = owned_transaction(db, user.id, transaction_id)
    validate_category(db, body.category_id, body.transaction_type)
    for key, value in body.model_dump(exclude={'source'}).items():
        setattr(record, key, value)
    db.commit()
    return owned_transaction(db, user.id, transaction_id)

@router.delete('/{transaction_id}', status_code=204)
def delete_transaction(transaction_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    record = owned_transaction(db, user.id, transaction_id)
    db.delete(record)
    db.commit()
    return Response(status_code=204)
