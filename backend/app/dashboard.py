import calendar
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload
from .database import get_db
from .models import Category, Transaction, User
from .schemas import TransactionRead
from .security import current_user

router = APIRouter(prefix='/api/dashboard', tags=['Dashboard'])

def month_offset(month: date, delta: int):
    index = month.year * 12 + month.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)

def money(value):
    return format(Decimal(value or 0), '.2f')

def percentage(current, previous):
    return round(float((current - previous) / abs(previous) * 100), 2) if previous else None

@router.get('')
def dashboard(month: date | None = Query(default=None, description='Any date in the selected month'), user: User = Depends(current_user), db: Session = Depends(get_db)):
    today = datetime.now(ZoneInfo('Asia/Colombo')).date()
    selected = (month or today).replace(day=1)
    if not 1900 <= selected.year <= 9998:
        raise HTTPException(422, 'Choose a dashboard month between 1900 and 9998')
    next_month = month_offset(selected, 1)
    previous = month_offset(selected, -1)
    first = month_offset(selected, -5)
    income_sum = func.coalesce(func.sum(case((Transaction.transaction_type == 'income', Transaction.amount), else_=0)), 0)
    expense_sum = func.coalesce(func.sum(case((Transaction.transaction_type == 'expense', Transaction.amount), else_=0)), 0)
    month_column = func.date_trunc('month', Transaction.transaction_date)
    totals = db.execute(select(month_column.label('month'), income_sum.label('income'), expense_sum.label('expense')).where(Transaction.user_id == user.id, Transaction.transaction_date >= first, Transaction.transaction_date < next_month).group_by(month_column)).all()
    lookup = {row.month.date(): (row.income, row.expense) for row in totals}
    income, expenses = lookup.get(selected, (Decimal(0), Decimal(0)))
    previous_income, previous_expenses = lookup.get(previous, (Decimal(0), Decimal(0)))
    balance_income, balance_expenses = db.execute(select(income_sum, expense_sum).where(Transaction.user_id == user.id, Transaction.transaction_date <= today)).one()
    category_rows = db.execute(select(Category.id, Category.name, func.sum(Transaction.amount).label('amount')).join(Transaction, Transaction.category_id == Category.id).where(Transaction.user_id == user.id, Transaction.transaction_type == 'expense', Transaction.transaction_date >= selected, Transaction.transaction_date < next_month).group_by(Category.id, Category.name).order_by(func.sum(Transaction.amount).desc(), Category.id)).all()
    daily_rows = db.execute(select(Transaction.transaction_date, func.sum(Transaction.amount)).where(Transaction.user_id == user.id, Transaction.transaction_type == 'expense', Transaction.transaction_date >= selected, Transaction.transaction_date < next_month).group_by(Transaction.transaction_date)).all()
    daily_lookup = dict(daily_rows)
    recent = db.scalars(select(Transaction).options(joinedload(Transaction.category)).where(Transaction.user_id == user.id, Transaction.transaction_date >= selected, Transaction.transaction_date < next_month).order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).limit(5)).all()
    monthly = []
    for offset in range(6):
        key = month_offset(first, offset)
        inc, exp = lookup.get(key, (Decimal(0), Decimal(0)))
        monthly.append({'month': key.isoformat(), 'income': money(inc), 'expenses': money(exp), 'savings': money(inc - exp)})
    return {
        'month': selected.isoformat(), 'as_of': today.isoformat(), 'currency': 'LKR',
        'balance': money(balance_income - balance_expenses), 'income': money(income), 'expenses': money(expenses), 'savings': money(income - expenses),
        'previous': {'month': previous.isoformat(), 'income': money(previous_income), 'expenses': money(previous_expenses), 'savings': money(previous_income - previous_expenses)},
        'changes': {'income': percentage(income, previous_income), 'expenses': percentage(expenses, previous_expenses), 'savings': percentage(income - expenses, previous_income - previous_expenses)},
        'categories': [{'id': row.id, 'name': row.name, 'amount': money(row.amount), 'percentage': round(float(row.amount / expenses * 100), 2) if expenses else 0} for row in category_rows],
        'top_category': category_rows[0].name if category_rows else None,
        'monthly': monthly,
        'daily': [{'date': date(selected.year, selected.month, day).isoformat(), 'expenses': money(daily_lookup.get(date(selected.year, selected.month, day), 0))} for day in range(1, calendar.monthrange(selected.year, selected.month)[1] + 1)],
        'recent_transactions': [TransactionRead.model_validate(row).model_dump(mode='json') for row in recent],
    }
