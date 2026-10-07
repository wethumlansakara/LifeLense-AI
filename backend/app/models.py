from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    transactions: Mapped[list['Transaction']] = relationship(back_populates='user', cascade='all, delete-orphan')
    saving_goals: Mapped[list['SavingGoal']] = relationship(back_populates='user', cascade='all, delete-orphan')

class Category(Base):
    __tablename__ = 'categories'
    __table_args__ = (CheckConstraint("type IN ('income', 'expense')"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[str] = mapped_column(String(10))
    icon: Mapped[str] = mapped_column(String(50))
    transactions: Mapped[list['Transaction']] = relationship(back_populates='category')

class Transaction(Base):
    __tablename__ = 'transactions'
    __table_args__ = (CheckConstraint('amount > 0'), CheckConstraint("transaction_type IN ('income', 'expense')"), Index('ix_transactions_user_date', 'user_id', 'transaction_date'))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'), index=True)
    description: Mapped[str] = mapped_column(String(500))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    transaction_type: Mapped[str] = mapped_column(String(10))
    transaction_date: Mapped[date]
    merchant: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(50), default='manual')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped['User'] = relationship(back_populates='transactions')
    category: Mapped['Category'] = relationship(back_populates='transactions')

class CategoryLabel(Base):
    __tablename__ = 'category_labels'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey('transactions.id', ondelete='CASCADE'), unique=True)
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'))
    description: Mapped[str] = mapped_column(String(500))
    merchant: Mapped[str] = mapped_column(String(200), default='')
    normalized_merchant: Mapped[str] = mapped_column(String(200), index=True)
    text: Mapped[str] = mapped_column(String(800))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class SpendingAnomaly(Base):
    __tablename__ = 'spending_anomalies'
    __table_args__ = (CheckConstraint('score >= 0 AND score <= 1'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey('transactions.id', ondelete='CASCADE'), unique=True)
    score: Mapped[float]
    explanation: Mapped[str] = mapped_column(String(1000))
    baseline: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    method: Mapped[str] = mapped_column(String(50))
    marked_normal: Mapped[bool] = mapped_column(default=False, server_default='false')
    active: Mapped[bool] = mapped_column(default=True, server_default='true')
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class SavingGoal(Base):
    __tablename__ = 'saving_goals'
    __table_args__ = (CheckConstraint('target_amount > 0'), CheckConstraint('saved_amount >= 0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    saved_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    target_date: Mapped[date]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped['User'] = relationship(back_populates='saving_goals')

class ChatTurn(Base):
    __tablename__ = 'chat_turns'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    question: Mapped[str] = mapped_column(String(1000))
    answer: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class FinancialReport(Base):
    __tablename__ = 'financial_reports'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    month: Mapped[date]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class RateLimitBucket(Base):
    __tablename__ = 'rate_limit_buckets'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
