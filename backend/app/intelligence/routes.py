import csv
import json
from io import StringIO
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Category, CategoryLabel, SpendingAnomaly, Transaction, User
from ..schemas import TransactionRead
from ..security import current_user
from ..transactions import owned_transaction
from .anomalies import scan_unusual
from .categorizer import MODEL_PATH, personal_model_path, save_label, suggest_category
from .forecast import predict_expenses
from .training import train_personal_model

router = APIRouter(prefix='/api/intelligence', tags=['Finance intelligence'])

class SuggestRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    description: str = Field(min_length=1, max_length=500)
    merchant: str = Field(default='', max_length=200)
    transaction_type: str = Field(default='expense', pattern='^(income|expense)$')

class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category_id: int = Field(gt=0)

class NormalRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    marked_normal: bool = True

@router.post('/suggest-category')
def suggest(body: SuggestRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return suggest_category(db, user.id, body.description, body.merchant, body.transaction_type)

@router.post('/transactions/{transaction_id}/category', response_model=TransactionRead)
def correct_category(transaction_id: int, body: CorrectionRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    record = owned_transaction(db, user.id, transaction_id)
    category = db.get(Category, body.category_id)
    if category is None or category.type != record.transaction_type:
        raise HTTPException(422, 'Category must match the transaction type')
    record.category_id = category.id
    db.flush()
    save_label(db, record)
    db.commit()
    return owned_transaction(db, user.id, transaction_id)

@router.get('/training-dataset')
def training_dataset(user: User = Depends(current_user), db: Session = Depends(get_db)):
    labels = db.execute(select(CategoryLabel, Category.name).join(Category, Category.id == CategoryLabel.category_id).where(CategoryLabel.user_id == user.id).order_by(CategoryLabel.id)).all()
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(['description', 'merchant', 'text', 'category', 'provenance'])
    for label, category in labels:
        # Prevent spreadsheet formula execution when a CSV is opened in Excel.
        values = [label.description, label.merchant, label.text, category, 'user-confirmed label']
        writer.writerow(["'" + value if value.startswith(('=', '+', '-', '@')) else value for value in values])
    return Response(content=stream.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="lifelens-training-labels.csv"', 'Cache-Control': 'no-store'})

@router.get('/model-status')
def model_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    personal = personal_model_path(db, user.id)
    model = personal if personal.exists() else MODEL_PATH
    metrics = model.with_name('category_metrics.json')
    return {'available': model.exists(), 'personal': personal.exists(), 'metadata': json.loads(metrics.read_text(encoding='utf-8')) if metrics.exists() else None}

@router.post('/train-category-model')
def train_category_model(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return train_personal_model(db, user.id)

@router.get('/forecast')
def forecast(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return predict_expenses(db, user.id)

@router.post('/unusual/scan')
def scan(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return scan_unusual(db, user.id)

@router.get('/unusual')
def unusual(include_normal: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    conditions = [SpendingAnomaly.user_id == user.id, SpendingAnomaly.active.is_(True), Transaction.user_id == user.id]
    if not include_normal:
        conditions.append(SpendingAnomaly.marked_normal.is_(False))
    rows = db.execute(select(SpendingAnomaly, Transaction).join(Transaction, Transaction.id == SpendingAnomaly.transaction_id).where(*conditions).order_by(SpendingAnomaly.score.desc(), SpendingAnomaly.id.desc()).limit(50)).all()
    return {'items': [{'id': anomaly.id, 'transaction': TransactionRead.model_validate(record).model_dump(mode='json'), 'score': anomaly.score, 'explanation': anomaly.explanation, 'baseline': str(anomaly.baseline), 'method': anomaly.method, 'marked_normal': anomaly.marked_normal} for anomaly, record in rows], 'limitations': 'Unusual transactions are statistical observations. New categories need at least five earlier expenses. They are not determinations of fraud.'}

@router.put('/unusual/{anomaly_id}/normal')
def mark_normal(anomaly_id: int, body: NormalRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    anomaly = db.scalar(select(SpendingAnomaly).where(SpendingAnomaly.id == anomaly_id, SpendingAnomaly.user_id == user.id))
    if anomaly is None:
        raise HTTPException(404, 'Unusual transaction not found')
    anomaly.marked_normal = body.marked_normal
    db.commit()
    return {'id': anomaly.id, 'marked_normal': anomaly.marked_normal}
