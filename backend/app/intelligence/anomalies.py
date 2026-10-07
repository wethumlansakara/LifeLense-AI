from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload
from ..models import SpendingAnomaly, Transaction
from .text import normalize_merchant

def scan_unusual(db, user_id):
    db.execute(text('SELECT pg_advisory_xact_lock(:namespace, :user_id)'), {'namespace': 1819043181, 'user_id': user_id})
    today = datetime.now(ZoneInfo('Asia/Colombo')).date()
    # Keep work bounded; process oldest to newest within the most recent 2,000 expenses.
    records = db.scalars(select(Transaction).options(joinedload(Transaction.category)).where(Transaction.user_id == user_id, Transaction.transaction_type == 'expense', Transaction.transaction_date <= today).order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).limit(2000)).all()[::-1]
    stored = {row.transaction_id: row for row in db.scalars(select(SpendingAnomaly).where(SpendingAnomaly.user_id == user_id)).all()}
    category_history, merchant_history = defaultdict(list), defaultdict(list)
    flagged = set()
    forest_evaluated = 0
    forest_cache = {}
    for record in records:
        canonical = normalize_merchant(record.merchant)
        category_values = category_history[record.category_id]
        merchant_values = merchant_history[canonical] if canonical else []
        references = []
        if len(category_values) >= 5:
            references.append(('category', category_values[-100:], record.category.name))
        if len(merchant_values) >= 5:
            references.append(('merchant', merchant_values[-100:], record.merchant))
        strongest = None
        for level, history, label in references:
            median = float(np.median(history))
            mad = float(np.median(np.abs(np.array(history) - median)))
            robust_scale = max(1.4826 * mad, median * .2, 100)
            threshold = max(median * 2.5, median + 3.5 * robust_scale)
            amount = float(record.amount)
            if amount > threshold and amount - median >= 1000:
                score = min(.99, .65 + .3 * (1 - threshold / amount))
                result = (score, median, f'Rs. {amount:,.2f} is {amount / median:.1f}× the median of your {len(history)} earlier {level} expenses for {label} (Rs. {median:,.2f}).', 'robust_statistics')
                if strongest is None or result[0] > strongest[0]:
                    strongest = result
        # Experimental secondary detector trained only on prior category amounts.
        if len(category_values) >= 20:
            cached = forest_cache.get(record.category_id)
            if cached is None or len(category_values) - cached[0] >= 20:
                history = np.log1p(np.array(category_values[-100:])).reshape(-1, 1)
                forest = IsolationForest(n_estimators=40, random_state=42, contamination=.05, n_jobs=1).fit(history)
                forest_cache[record.category_id] = (len(category_values), forest)
            else:
                forest = cached[1]
            value = np.array([[np.log1p(float(record.amount))]])
            forest_score = float(forest.decision_function(value)[0])
            forest_evaluated += 1
            median = float(np.median(category_values[-100:]))
            if strongest is None and forest_score < 0 and float(record.amount) > median * 2 and float(record.amount) - median >= 1000:
                strongest = (min(.9, .6 + abs(forest_score)), median, f'Rs. {float(record.amount):,.2f} is above your earlier {record.category.name} median of Rs. {median:,.2f}; an experimental Isolation Forest also marked this amount as unusual.', 'isolation_forest')
        if strongest:
            flagged.add(record.id)
            anomaly = stored.get(record.id)
            if anomaly is None:
                anomaly = SpendingAnomaly(user_id=user_id, transaction_id=record.id, marked_normal=False)
                db.add(anomaly)
            anomaly.score, baseline, anomaly.explanation, anomaly.method = strongest
            anomaly.baseline = Decimal(str(round(baseline, 2)))
            anomaly.active = True
        # A past flagged outlier cannot inflate future baselines unless explicitly marked normal.
        previous = stored.get(record.id)
        if strongest is None or previous and previous.marked_normal:
            category_history[record.category_id].append(float(record.amount))
            if canonical:
                merchant_history[canonical].append(float(record.amount))
    for transaction_id, anomaly in stored.items():
        if transaction_id not in flagged:
            anomaly.active = False
    db.commit()
    return {'expenses_reviewed': len(records), 'flagged': len(flagged), 'isolation_forest_evaluations': forest_evaluated, 'limitations': 'At least 5 earlier category or merchant expenses are required. Up to 2,000 recent expenses are reviewed. Scores are heuristics, not probabilities.'}
