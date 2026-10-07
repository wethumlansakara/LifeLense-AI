import math
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import func, select
from ..dashboard import money, month_offset
from ..models import Transaction

def features(values, month, index):
    return [values[-1], values[-2], np.mean(values[-3:]), index, math.sin(2 * math.pi * month.month / 12), math.cos(2 * math.pi * month.month / 12)]

def fit_regression(values, months):
    x = [features(values[:i], months[i], i) for i in range(3, len(values))]
    model = make_pipeline(StandardScaler(), Ridge(alpha=10))
    model.fit(x, values[3:])
    return model

def predict_expenses(db, user_id, as_of=None):
    today = as_of or datetime.now(ZoneInfo('Asia/Colombo')).date()
    current = today.replace(day=1)
    target = month_offset(current, 1)
    earliest = db.scalar(select(func.min(Transaction.transaction_date)).where(Transaction.user_id == user_id, Transaction.transaction_type == 'expense', Transaction.transaction_date < current))
    limitations = ['Only your recorded expenses are used; missing records can bias this estimate.', 'The incomplete current month is excluded. Unrecorded historical months are treated as zero.', 'The planning range is heuristic, not a calibrated confidence interval.']
    if earliest is None:
        return {'target_month': target.isoformat(), 'prediction': None, 'method': 'insufficient_history', 'confidence': 'unavailable', 'history': [], 'training_months': 0, 'active_months': 0, 'range': None, 'evaluation': None, 'limitations': limitations + ['Add expenses from completed months to get an estimate.']}
    first = max(earliest.replace(day=1), month_offset(current, -36))
    month_column = func.date_trunc('month', Transaction.transaction_date)
    rows = db.execute(select(month_column, func.sum(Transaction.amount)).where(Transaction.user_id == user_id, Transaction.transaction_type == 'expense', Transaction.transaction_date >= first, Transaction.transaction_date < current).group_by(month_column)).all()
    lookup = {row[0].date(): row[1] for row in rows}
    months = []
    cursor = first
    while cursor < current:
        months.append(cursor)
        cursor = month_offset(cursor, 1)
    values = [float(lookup.get(month, Decimal(0))) for month in months]
    active = sum(value > 0 for value in values)
    baseline = float(np.mean(values[-3:]))
    method = 'simple_average'
    prediction = baseline
    evaluation = None
    if len(values) >= 12 and active >= 9:
        actuals, regression_predictions, baseline_predictions = [], [], []
        # Expanding-window backtest: every prediction uses strictly earlier months.
        for i in range(max(9, len(values) - 6), len(values)):
            model = fit_regression(values[:i], months[:i])
            regression_predictions.append(max(0, float(model.predict([features(values[:i], months[i], i)])[0])))
            baseline_predictions.append(float(np.mean(values[max(0, i - 3):i])))
            actuals.append(values[i])
        evaluation = {'test_months': len(actuals), 'split': 'expanding chronological windows', 'baseline': {'mae': round(mean_absolute_error(actuals, baseline_predictions), 2), 'rmse': round(root_mean_squared_error(actuals, baseline_predictions), 2)}, 'regression': {'mae': round(mean_absolute_error(actuals, regression_predictions), 2), 'rmse': round(root_mean_squared_error(actuals, regression_predictions), 2)}}
        if evaluation['regression']['mae'] < evaluation['baseline']['mae'] * .95:
            method = 'ridge_regression'
            model = fit_regression(values, months)
            forecast_values = values.copy()
            # Bridge the excluded current month before forecasting next month.
            for step in (current, target):
                prediction = max(0, float(model.predict([features(forecast_values, step, len(forecast_values))])[0]))
                forecast_values.append(prediction)
        else:
            limitations.append('Regression did not beat the average in the backtest, so the average is shown.')
    else:
        limitations.append('At least 12 completed months and 9 months with recorded expenses are needed to evaluate regression. A recent-month average is shown instead.')
    # Wide ranges intentionally convey sparse/uncertain history rather than false precision.
    error = evaluation['regression' if method == 'ridge_regression' else 'baseline']['rmse'] if evaluation else float(np.std(values[-6:]))
    width = max(error * 1.5, prediction * (.25 if len(values) >= 12 else .5))
    return {'target_month': target.isoformat(), 'prediction': money(Decimal(str(prediction))), 'method': method, 'confidence': 'moderate' if method == 'ridge_regression' and len(values) >= 18 else 'low', 'history': [{'month': month.isoformat(), 'expenses': money(lookup.get(month, 0))} for month in months], 'training_months': len(months), 'active_months': active, 'range': {'low': money(Decimal(str(max(0, prediction - width)))), 'high': money(Decimal(str(prediction + width)))}, 'evaluation': evaluation, 'limitations': limitations, 'trained_through': months[-1].isoformat()}
