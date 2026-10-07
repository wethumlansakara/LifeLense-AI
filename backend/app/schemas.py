from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Name cannot be blank')
        return value

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'

class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    type: Literal['income', 'expense']
    icon: str

class TransactionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category_id: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    transaction_type: Literal['income', 'expense']
    transaction_date: date
    merchant: str | None = Field(default=None, max_length=200)
    source: str = Field(default='manual', min_length=1, max_length=50)

    @field_validator('description', 'merchant')
    @classmethod
    def clean_text(cls, value, info):
        if value is None:
            return None
        value = value.strip()
        if info.field_name == 'description' and not value:
            raise ValueError('Description cannot be blank')
        return value or None

class TransactionRead(TransactionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    created_at: datetime
    category: CategoryRead

class TransactionPage(BaseModel):
    items: list[TransactionRead]
    total: int
    page: int
    page_size: int
    pages: int

class ImportConfirm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: Literal['csv', 'xlsx']
    transactions: list[TransactionCreate] = Field(min_length=1, max_length=2000)

class SavingGoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    saved_amount: Decimal = Field(default=Decimal('0'), ge=0, max_digits=14, decimal_places=2)
    target_date: date

class SavingGoalRead(SavingGoalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    created_at: datetime
