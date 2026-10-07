from functools import lru_cache
from datetime import timezone
from hashlib import sha256
from pathlib import Path
import joblib
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from ..models import Category, CategoryLabel, User
from .text import normalize_merchant, preprocess, rule_category

MODEL_PATH = Path(__file__).resolve().parents[3] / 'ml' / 'artifacts' / 'category_model.joblib'

def personal_model_path(db, user_id):
    user = db.get(User, user_id)
    identity = f'{user.email}:{user.created_at.astimezone(timezone.utc).isoformat()}'
    namespace = sha256(identity.encode()).hexdigest()[:16]
    return MODEL_PATH.parent / 'users' / f'{user_id}-{namespace}' / MODEL_PATH.name

@lru_cache(maxsize=8)
def load_model(path, modified):
    # Only load the locally trained, trusted artifact, never a user-uploaded pickle.
    return joblib.load(path)

def suggest_category(db, user_id, description, merchant='', direction='expense', categories=None, labels=None):
    categories = {category.name: category for category in (categories if categories is not None else db.scalars(select(Category)).all())}
    canonical = normalize_merchant(merchant)
    cleaned = preprocess(f'{merchant or ""} {description}')[:800]
    if direction == 'income':
        return suggestion(categories, 'Salary', 1, 'income', 'Default income category; you can change it.', canonical)
    # Personal labels can override generic rules without exposing another user's labels.
    condition = CategoryLabel.normalized_merchant == canonical if canonical else CategoryLabel.text == cleaned
    if not canonical and not cleaned:
        label = None
    elif labels is None:
        label = db.scalar(select(CategoryLabel).join(Category, Category.id == CategoryLabel.category_id).where(CategoryLabel.user_id == user_id, Category.type == 'expense', condition).order_by(CategoryLabel.updated_at.desc(), CategoryLabel.id.desc()).limit(1))
    else:
        expense_ids = {c.id for c in categories.values() if c.type == 'expense'}
        label = next((row for row in labels if row.user_id == user_id and row.category_id in expense_ids and (row.normalized_merchant == canonical if canonical else row.text == cleaned)), None)
    if label:
        category = next((c for c in categories.values() if c.id == label.category_id), None)
        if category:
            return suggestion(categories, category.name, .99, 'personal_correction', 'Based on a category you previously confirmed for this merchant or description.', canonical)
    matched = rule_category(description, merchant)
    if matched:
        name, confidence, reason = matched
        return suggestion(categories, name, confidence, 'rule', reason, canonical)
    personal = personal_model_path(db, user_id)
    model_path = personal if personal.exists() else MODEL_PATH
    if model_path.exists():
        artifact = load_model(str(model_path), model_path.stat().st_mtime_ns)
        pipeline = artifact['pipeline']
        vector = pipeline.named_steps['tfidf'].transform([cleaned])
        if vector.nnz:
            probabilities = pipeline.predict_proba([cleaned])[0]
            index = int(probabilities.argmax())
            confidence = float(probabilities[index])
            name = str(pipeline.classes_[index])
            if confidence >= .45 and name in categories and categories[name].type == 'expense':
                result = suggestion(categories, name, round(confidence, 3), 'ml', 'TF-IDF text classifier suggestion. Confidence is an uncalibrated model score; please review.', canonical)
                result['model_dataset'] = artifact['metadata']['dataset']
                if personal.exists():
                    result['limitations'] = 'Your private model uses confirmed labels. Small holdout metrics and uncalibrated scores do not guarantee accuracy on new transactions.'
                return result
    return suggestion(categories, 'Other', 0, 'fallback', 'No reliable match. Choose the category that fits.', canonical)

def suggestion(categories, name, confidence, method, reason, canonical):
    category = categories.get(name)
    return {'category_id': category.id if category else None, 'category_name': name, 'confidence': confidence, 'method': method, 'reason': reason, 'normalized_merchant': canonical, 'limitations': 'Rules use heuristic scores. The starter ML model is evaluated on synthetic examples, not real bank statements.'}

def save_label(db, record):
    if record.transaction_type != 'expense':
        db.execute(delete(CategoryLabel).where(CategoryLabel.transaction_id == record.id, CategoryLabel.user_id == record.user_id))
        return
    values = {'user_id': record.user_id, 'transaction_id': record.id, 'category_id': record.category_id, 'description': record.description, 'merchant': record.merchant or '', 'normalized_merchant': normalize_merchant(record.merchant), 'text': preprocess(f'{record.merchant or ""} {record.description}')[:800]}
    statement = insert(CategoryLabel).values(**values)
    from sqlalchemy import func
    db.execute(statement.on_conflict_do_update(index_elements=['transaction_id'], set_={**values, 'updated_at': func.now()}))
