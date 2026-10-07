from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import get_db
from .models import SavingGoal, User
from .security import current_user

router = APIRouter(prefix='/api/goals', tags=['Saving goals'])

def today():
    return datetime.now(ZoneInfo('Asia/Colombo')).date()

class GoalInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    target_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    saved_amount: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=2)
    target_date: date

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('Enter a goal name')
        return value.strip()

class Deposit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)

def owned(db, user_id, goal_id, lock=False):
    query = select(SavingGoal).where(SavingGoal.id == goal_id, SavingGoal.user_id == user_id)
    if lock:
        query = query.with_for_update()
    goal = db.scalar(query)
    if not goal:
        raise HTTPException(404, 'Goal not found')
    return goal

def serialize(goal):
    remaining = max(Decimal(0), goal.target_amount - goal.saved_amount)
    now = today()
    months = max(1, (goal.target_date.year-now.year)*12 + goal.target_date.month-now.month + (goal.target_date.day > now.day))
    return {'id': goal.id, 'name': goal.name, 'target_amount': str(goal.target_amount),
            'saved_amount': str(goal.saved_amount), 'target_date': goal.target_date.isoformat(),
            'remaining': str(remaining), 'progress': round(float(goal.saved_amount/goal.target_amount*100), 2),
            'months_remaining': months, 'required_monthly': str((remaining/months).quantize(Decimal('.01'), rounding=ROUND_CEILING)),
            'overdue': goal.target_date < now and remaining > 0}

@router.get('')
def list_goals(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [serialize(g) for g in db.scalars(select(SavingGoal).where(SavingGoal.user_id == user.id).order_by(SavingGoal.target_date, SavingGoal.id))]

@router.post('', status_code=201)
def create_goal(body: GoalInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal = SavingGoal(user_id=user.id, **body.model_dump())
    db.add(goal); db.commit(); db.refresh(goal)
    return serialize(goal)

@router.put('/{goal_id}')
def edit_goal(goal_id: int, body: GoalInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal = owned(db, user.id, goal_id, True)
    for key, value in body.model_dump().items():
        setattr(goal, key, value)
    db.commit(); db.refresh(goal)
    return serialize(goal)

@router.post('/{goal_id}/funds')
def add_funds(goal_id: int, body: Deposit, db: Session = Depends(get_db), user: User = Depends(current_user)):
    goal = owned(db, user.id, goal_id, True)
    if goal.saved_amount + body.amount >= Decimal('1000000000000'):
        raise HTTPException(422, 'Saved amount exceeds supported limit')
    goal.saved_amount += body.amount
    db.commit(); db.refresh(goal)
    return serialize(goal)

@router.delete('/{goal_id}', status_code=204)
def delete_goal(goal_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(owned(db, user.id, goal_id, True)); db.commit()
