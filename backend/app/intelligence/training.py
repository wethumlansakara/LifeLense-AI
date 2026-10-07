import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import joblib
from fastapi import HTTPException
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sqlalchemy import select
from ..models import Category, CategoryLabel
from .categorizer import MODEL_PATH, personal_model_path
from .text import preprocess

def train_personal_model(db, user_id):
    rows = db.execute(select(CategoryLabel, Category.name).join(Category, Category.id == CategoryLabel.category_id).where(CategoryLabel.user_id == user_id, Category.type == 'expense').order_by(CategoryLabel.updated_at.desc(), CategoryLabel.id.desc()).limit(1000)).all()
    # Most recent label wins for identical text; duplicated text cannot leak across the split.
    examples = {}
    for label, category in rows:
        key = preprocess(f'{label.merchant} {label.description}')[:800]
        if key:
            examples.setdefault(key, category)
    counts = Counter(examples.values())
    if len(examples) < 20 or len(counts) < 2 or min(counts.values()) < 4:
        raise HTTPException(422, 'Personal training needs at least 20 distinct confirmed expense examples, at least 2 categories, and at least 4 examples in each category.')
    texts, labels = list(examples), list(examples.values())
    x_train, x_test, y_train, y_test = train_test_split(texts, labels, test_size=max(.25, len(counts) / len(texts)), stratify=labels, random_state=42)
    pipelines, scores = {}, {}
    for name, classifier in {'logistic_regression': LogisticRegression(C=8, max_iter=1000, random_state=42), 'random_forest': RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced', n_jobs=1)}.items():
        pipeline = Pipeline([('tfidf', TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, max_features=5000)), ('classifier', classifier)])
        pipeline.fit(x_train, y_train)
        prediction = pipeline.predict(x_test)
        scores[name] = {'accuracy': accuracy_score(y_test, prediction), 'macro_f1': f1_score(y_test, prediction, average='macro', zero_division=0), 'report': classification_report(y_test, prediction, output_dict=True, zero_division=0)}
        pipelines[name] = pipeline
    winner = max(scores, key=lambda name: (scores[name]['macro_f1'], scores[name]['accuracy']))
    pipelines[winner].fit(texts, labels)
    metadata = {'trained_at': datetime.now(timezone.utc).isoformat(), 'selected_model': winner, 'samples': len(texts), 'held_out_samples': len(x_test), 'dataset': 'your private confirmed labels', 'metrics': scores, 'limitations': 'Scores come from a small text-deduplicated holdout of your labels. Merchant/domain overlap may still inflate accuracy; scores are not calibrated probabilities.'}
    output = personal_model_path(db, user_id).parent
    output.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents a suggestion request reading a half-written model.
    temporary = output / f'{uuid.uuid4().hex}.tmp'
    try:
        joblib.dump({'pipeline': pipelines[winner], 'metadata': metadata}, temporary)
        temporary.replace(output / MODEL_PATH.name)
    finally:
        temporary.unlink(missing_ok=True)
    metrics_temporary = output / f'{uuid.uuid4().hex}.json'
    try:
        metrics_temporary.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        metrics_temporary.replace(output / 'category_metrics.json')
    finally:
        metrics_temporary.unlink(missing_ok=True)
    return metadata
