import csv
import uuid
from datetime import date
from decimal import Decimal
from io import StringIO
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from app.database import SessionLocal
from app.dashboard import month_offset
from app.intelligence.forecast import predict_expenses
from app.intelligence.text import normalize_merchant, preprocess, rule_category
from app.intelligence.categorizer import MODEL_PATH, personal_model_path
from app.main import app
from app.models import Transaction, User
from app.seed import seed

client = TestClient(app)

@pytest.fixture
def users():
    seed()
    accounts = []
    for _ in range(2):
        email = f'intelligence-{uuid.uuid4().hex}@example.com'
        payload = {'name': 'Intelligence Test', 'email': email, 'password': 'intelligence-test-password'}
        user = client.post('/api/auth/register', json=payload).json()
        token = client.post('/api/auth/login', json={'email': email, 'password': payload['password']}).json()['access_token']
        accounts.append((user['id'], {'Authorization': f'Bearer {token}'}))
    categories = {c['name']: c['id'] for c in client.get('/api/categories', headers=accounts[0][1]).json()}
    yield accounts, categories
    with SessionLocal() as db:
        model_directories = [personal_model_path(db, account_id).parent for account_id, _ in accounts]
        db.execute(delete(User).where(User.id.in_([account[0] for account in accounts])))
        db.commit()
    for model_dir in model_directories:
        if model_dir.exists():
            for file in model_dir.iterdir():
                if file.is_file():
                    file.unlink()
            model_dir.rmdir()

def transaction(headers, categories, **updates):
    body = {'description': 'Dinner', 'merchant': 'Garden Cafe', 'amount': '2000', 'transaction_type': 'expense', 'transaction_date': '2026-09-01', 'category_id': categories['Food']} | updates
    response = client.post('/api/transactions', headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()

def test_rules_normalization_and_no_substring_false_positives():
    assert normalize_merchant('POS UBER *Trip 8293 Colombo') == 'uber'
    assert normalize_merchant('Pick Me ride #3498') == 'pickme'
    assert preprocess('Café POS Payment REF 987') == 'cafe'
    assert rule_category('tuber seeds', '') is None
    expected = {'Uber': 'Transport', 'PickMe': 'Transport', 'Keells': 'Groceries', 'Cargills': 'Groceries', 'Netflix': 'Entertainment', 'Spotify': 'Entertainment', 'Dialog': 'Bills'}
    for merchant, category in expected.items():
        assert rule_category('Card purchase', merchant)[0] == category

def test_suggestions_corrections_private_dataset_and_ml(users):
    ((user_id, owner), (_, other)), categories = users
    payload = {'description': 'Card purchase', 'merchant': 'KEELLS Colombo 123'}
    initial = client.post('/api/intelligence/suggest-category', headers=owner, json=payload).json()
    assert initial['category_name'] == 'Groceries' and initial['method'] == 'rule'
    record = transaction(owner, categories, category_id=None, description='Card purchase', merchant='KEELLS Colombo 123')
    assert record['category_id'] == categories['Groceries']
    corrected = client.post(f"/api/intelligence/transactions/{record['id']}/category", headers=owner, json={'category_id': categories['Shopping']})
    assert corrected.status_code == 200
    learned = client.post('/api/intelligence/suggest-category', headers=owner, json=payload).json()
    assert learned['category_name'] == 'Shopping' and learned['method'] == 'personal_correction'
    assert client.post('/api/intelligence/suggest-category', headers=other, json=payload).json()['category_name'] == 'Groceries'
    assert client.post(f"/api/intelligence/transactions/{record['id']}/category", headers=other, json={'category_id': categories['Food']}).status_code == 404
    assert client.post(f"/api/intelligence/transactions/{record['id']}/category", headers=owner, json={'category_id': categories['Salary']}).status_code == 422
    rows = list(csv.DictReader(StringIO(client.get('/api/intelligence/training-dataset', headers=owner).text)))
    assert len(rows) == 1 and rows[0]['category'] == 'Shopping'
    assert list(csv.DictReader(StringIO(client.get('/api/intelligence/training-dataset', headers=other).text))) == []
    status = client.get('/api/intelligence/model-status', headers=owner).json()
    assert status['available'] and status['metadata']['dataset'] == 'synthetic starter examples'
    assert set(status['metadata']['metrics']) == {'logistic_regression', 'random_forest'}
    ml = client.post('/api/intelligence/suggest-category', headers=owner, json={'description': 'semester learning fees'}).json()
    assert ml['method'] == 'ml' and ml['category_name'] == 'Education' and 0 <= ml['confidence'] <= 1
    fallback = client.post('/api/intelligence/suggest-category', headers=owner, json={'description': 'zxqv blorpf zzzz'}).json()
    assert fallback['category_name'] == 'Other' and fallback['confidence'] == 0
    assert client.post('/api/intelligence/suggest-category', json=payload).status_code == 401
    assert client.get('/api/intelligence/training-dataset').status_code == 401
    assert client.post('/api/intelligence/suggest-category', headers=owner, json=payload | {'user_id': user_id}).status_code == 422

def test_labels_refresh_on_edit_and_spreadsheet_safe_export(users):
    ((_, owner), _), categories = users
    record = transaction(owner, categories, description='=SUM(A1)', merchant='Custom shop')
    text = client.get('/api/intelligence/training-dataset', headers=owner).text
    assert "'=SUM(A1)" in text
    edit = {key: record[key] for key in ['description', 'merchant', 'amount', 'transaction_type', 'transaction_date', 'category_id']}
    edit.update(transaction_type='income', category_id=categories['Salary'])
    assert client.put(f"/api/transactions/{record['id']}", headers=owner, json=edit).status_code == 200
    assert len(list(csv.DictReader(StringIO(client.get('/api/intelligence/training-dataset', headers=owner).text)))) == 0

def test_import_suggestions_and_only_corrected_labels_saved(users):
    ((_, owner), _), categories = users
    preview = client.post('/api/imports/preview', headers=owner, files={'file': ('statement.csv', b'Date,Description,Merchant,Amount\n05/09/2026,Ride,Uber,1200\n', 'text/csv')}).json()
    row = preview['rows'][0]
    assert row['suggestion']['method'] == 'rule' and row['suggestion']['confidence'] >= .95
    entry = row['transaction'] | {'category_id': categories['Travel'], 'category_confirmed': True}
    assert client.post('/api/imports/confirm', headers=owner, json={'source': 'csv', 'transactions': [entry]}).json()['imported'] == 1
    learned = client.post('/api/intelligence/suggest-category', headers=owner, json={'description': 'Ride', 'merchant': 'Uber'}).json()
    assert learned['category_name'] == 'Travel'

def test_forecast_cold_start_average_incomplete_month_and_ownership(users):
    ((user_id, owner), (other_id, other)), categories = users
    assert client.get('/api/intelligence/forecast', headers=owner).json()['prediction'] is None
    transaction(owner, categories, amount='600', transaction_date='2026-09-01')
    transaction(owner, categories, amount='900000', transaction_date='2026-10-01')
    transaction(other, categories, amount='99000', transaction_date='2026-09-01')
    with SessionLocal() as db:
        forecast = predict_expenses(db, user_id, as_of=date(2026, 10, 7))
        assert forecast['target_month'] == '2026-11-01'
        assert forecast['prediction'] == '600.00' and forecast['method'] == 'simple_average'
        assert forecast['confidence'] == 'low' and forecast['training_months'] == 1
        assert forecast['evaluation'] is None
        assert predict_expenses(db, other_id, as_of=date(2026, 10, 7))['prediction'] == '99000.00'
    assert client.get('/api/intelligence/forecast').status_code == 401

def test_regression_chronological_backtest_metrics_and_missing_months(users):
    ((user_id, _), _), categories = users
    with SessionLocal() as db:
        for index in range(21):
            month = month_offset(date(2025, 1, 1), index)
            db.add(Transaction(user_id=user_id, category_id=categories['Food'], description='Historical expenses', merchant='Cafe', amount=Decimal(10000 + index * 1200), transaction_date=month, transaction_type='expense', source='manual'))
        db.commit()
        result = predict_expenses(db, user_id, as_of=date(2026, 10, 7))
        assert result['training_months'] == 21 and result['active_months'] == 21
        assert result['evaluation']['split'] == 'expanding chronological windows'
        assert result['evaluation']['test_months'] == 6
        for model in ['baseline', 'regression']:
            assert result['evaluation'][model]['mae'] >= 0
            assert result['evaluation'][model]['rmse'] >= result['evaluation'][model]['mae'] - .01
        assert result['method'] == 'ridge_regression'
        assert float(result['range']['low']) <= float(result['prediction']) <= float(result['range']['high'])
        db.add(Transaction(user_id=user_id, category_id=categories['Food'], description='Current partial month', amount=Decimal(999999), transaction_date=date(2026, 10, 1), transaction_type='expense', source='manual'))
        db.commit()
        assert predict_expenses(db, user_id, as_of=date(2026, 10, 7))['prediction'] == result['prediction']

def test_unusual_spending_explanations_normal_override_and_owner_checks(users):
    ((_, owner), (_, other)), categories = users
    for index, amount in enumerate([1000, 2000, 3000, 2500, 1800], start=1):
        transaction(owner, categories, amount=str(amount), transaction_date=f'2026-09-{index:02d}')
    unusual = transaction(owner, categories, amount='18500', transaction_date='2026-09-06')
    # Future expenses and incomes are never used as normal expense behavior.
    transaction(owner, categories, amount='99999', transaction_date='2027-01-01')
    scanned = client.post('/api/intelligence/unusual/scan', headers=owner).json()
    assert scanned['expenses_reviewed'] == 6 and scanned['flagged'] == 1
    response = client.get('/api/intelligence/unusual', headers=owner).json()
    alert = response['items'][0]
    assert alert['transaction']['id'] == unusual['id']
    assert 'median' in alert['explanation'] and 'earlier' in alert['explanation']
    assert .65 <= alert['score'] <= 1 and alert['method'] == 'robust_statistics'
    assert client.get('/api/intelligence/unusual', headers=other).json()['items'] == []
    assert client.put(f"/api/intelligence/unusual/{alert['id']}/normal", headers=other, json={'marked_normal': True}).status_code == 404
    assert client.put(f"/api/intelligence/unusual/{alert['id']}/normal", headers=owner, json={'marked_normal': True}).json()['marked_normal']
    client.post('/api/intelligence/unusual/scan', headers=owner)
    assert client.get('/api/intelligence/unusual', headers=owner).json()['items'] == []
    assert client.get('/api/intelligence/unusual?include_normal=true', headers=owner).json()['items'][0]['marked_normal']
    assert client.put(f"/api/intelligence/unusual/{alert['id']}/normal", headers=owner, json={'marked_normal': False}).status_code == 200
    assert client.get('/api/intelligence/unusual', headers=owner).json()['items']
    edit = {key: unusual[key] for key in ['description', 'merchant', 'amount', 'transaction_type', 'transaction_date', 'category_id']}; edit['amount'] = '2000'
    assert client.put(f"/api/transactions/{unusual['id']}", headers=owner, json=edit).status_code == 200
    client.post('/api/intelligence/unusual/scan', headers=owner)
    assert client.get('/api/intelligence/unusual?include_normal=true', headers=owner).json()['items'] == []
    assert client.post('/api/intelligence/unusual/scan').status_code == 401

def test_isolation_forest_experiment_is_bounded_and_repeatable(users):
    ((user_id, owner), _), categories = users
    with SessionLocal() as db:
        for index in range(22):
            db.add(Transaction(user_id=user_id, category_id=categories['Food'], description='Typical lunch', merchant='Cafe', amount=Decimal(2000 + index % 5 * 100), transaction_type='expense', transaction_date=date(2026, 9, index + 1), source='manual'))
        db.commit()
    first = client.post('/api/intelligence/unusual/scan', headers=owner).json()
    second = client.post('/api/intelligence/unusual/scan', headers=owner).json()
    assert first == second and first['isolation_forest_evaluations'] == 2
    assert first['flagged'] == 0

def test_private_model_training_thresholds_artifacts_and_isolation(users):
    ((user_id, owner), (_, other)), categories = users
    assert client.post('/api/intelligence/train-category-model', headers=owner).status_code == 422
    food_texts = ['breakfast sandwich meal', 'lunch rice curry meal', 'dinner noodles meal', 'dessert cake takeaway', 'fresh juice smoothie snack', 'burger fries takeaway', 'sushi dinner meal', 'pasta lunch meal', 'tea pastry snack', 'salad bowl lunch']
    shopping_texts = ['new jacket fashion', 'mobile phone accessories', 'home furniture order', 'laptop gadget order', 'sportswear fashion order', 'kitchen appliance order', 'new trousers fashion', 'headphones gadget order', 'office chair furniture', 'watch fashion accessories']
    for category, texts in [('Food', food_texts), ('Shopping', shopping_texts)]:
        for text in texts:
            transaction(owner, categories, description=text, merchant=text, category_id=categories[category])
    result = client.post('/api/intelligence/train-category-model', headers=owner)
    assert result.status_code == 200, result.text
    metadata = result.json()
    assert metadata['samples'] == 20 and metadata['dataset'] == 'your private confirmed labels'
    assert set(metadata['metrics']) == {'logistic_regression', 'random_forest'}
    with SessionLocal() as db:
        assert personal_model_path(db, user_id).exists()
    assert client.get('/api/intelligence/model-status', headers=owner).json()['personal']
    assert not client.get('/api/intelligence/model-status', headers=other).json()['personal']
    assert client.post('/api/intelligence/train-category-model', headers=other).status_code == 422
    assert client.post('/api/intelligence/train-category-model').status_code == 401
