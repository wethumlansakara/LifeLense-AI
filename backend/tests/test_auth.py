import uuid
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import User
from app.models import Category, Transaction, SavingGoal
from sqlalchemy.exc import IntegrityError
from datetime import date
from decimal import Decimal
from app.seed import seed
from app.security import password_hash

@pytest.fixture
def accounts():
    emails = [f'test-{uuid.uuid4().hex}@example.com' for _ in range(2)]
    yield emails
    with SessionLocal() as db:
        db.execute(delete(User).where(User.email.in_(emails)))
        db.commit()

client = TestClient(app)

def test_database_and_categories():
    assert client.get('/api/health').json() == {'status': 'ok', 'database': 'connected'}
    seed()
    seed()
    assert client.get('/api/categories').status_code == 401

def test_registration_login_isolation_and_validation(accounts):
    password = 'a-long-unique-test-passphrase'
    tokens = []
    ids = []
    for email in accounts:
        response = client.post('/api/auth/register', json={'name': 'Test User', 'email': email, 'password': password})
        assert response.status_code == 201
        assert 'password_hash' not in response.json()
        ids.append(response.json()['id'])
        login = client.post('/api/auth/login', json={'email': email, 'password': password})
        assert login.status_code == 200
        tokens.append(login.json()['access_token'])
    assert ids[0] != ids[1]
    for email, token, user_id in zip(accounts, tokens, ids):
        headers = {'Authorization': f'Bearer {token}'}
        me = client.get('/api/auth/me', headers=headers)
        assert me.json()['email'] == email
        assert me.json()['id'] == user_id
        assert len(client.get('/api/categories', headers=headers).json()) == 11
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            assert user.password_hash != password
            assert user.password_hash.startswith('$argon2')
            assert password_hash.verify(password, user.password_hash)
    assert client.post('/api/auth/register', json={'name': 'Duplicate', 'email': accounts[0].upper(), 'password': password}).status_code == 409
    invalid = client.post('/api/auth/register', json={'name': ' ', 'email': 'bad', 'password': 'short'})
    assert invalid.status_code == 422
    assert all('input' not in error for error in invalid.json()['detail'])
    assert client.post('/api/auth/login', json={'email': accounts[0], 'password': 'wrong'}).status_code == 401
    assert client.get('/api/auth/me').status_code == 401
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer invalid'}).status_code == 401
    assert client.get('/api/auth/me', headers={'Authorization': f'Bearer {tokens[0]}tampered'}).status_code == 401
    expired = jwt.encode({'sub': str(ids[0]), 'iat': datetime.now(timezone.utc) - timedelta(hours=2), 'exp': datetime.now(timezone.utc) - timedelta(hours=1)}, settings.jwt_secret, algorithm='HS256')
    assert client.get('/api/auth/me', headers={'Authorization': f'Bearer {expired}'}).status_code == 401

def test_financial_models_relationships_and_constraints(accounts):
    seed()
    with SessionLocal() as db:
        user = User(name='Model Test', email=accounts[0], password_hash=password_hash.hash('long-model-test-password'))
        category = db.scalar(select(Category).where(Category.name == 'Food'))
        db.add(user)
        db.flush()
        transaction = Transaction(user=user, category=category, description='Lunch', amount=Decimal('12.34'), transaction_type='expense', transaction_date=date.today())
        goal = SavingGoal(user=user, name='Emergency fund', target_amount=Decimal('1000.00'), target_date=date(2027, 1, 1))
        db.add_all([transaction, goal])
        db.commit()
        assert user.transactions[0].amount == Decimal('12.34')
        assert user.saving_goals[0].saved_amount == Decimal('0.00')
        assert transaction.category.name == 'Food'
        transaction.amount = Decimal('-1')
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        user_id, transaction_id, goal_id = user.id, transaction.id, goal.id
        db.execute(delete(User).where(User.id == user_id))
        db.commit()
        db.expire_all()
        assert db.get(Transaction, transaction_id) is None
        assert db.get(SavingGoal, goal_id) is None
