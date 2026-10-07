import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
from zipfile import ZipFile
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import delete
from app.database import SessionLocal
from app.main import app
from app.models import User
from app.seed import seed

client = TestClient(app)

@pytest.fixture
def owners():
    seed()
    emails = [f'finance-{uuid.uuid4().hex}@example.com' for _ in range(2)]
    headers = []
    for email in emails:
        payload = {'name': 'Finance Test', 'email': email, 'password': 'finance-test-long-password'}
        assert client.post('/api/auth/register', json=payload).status_code == 201
        token = client.post('/api/auth/login', json={'email': email, 'password': payload['password']}).json()['access_token']
        headers.append({'Authorization': f'Bearer {token}'})
    categories = {c['name']: c['id'] for c in client.get('/api/categories', headers=headers[0]).json()}
    yield headers, categories
    with SessionLocal() as db:
        db.execute(delete(User).where(User.email.in_(emails)))
        db.commit()

def entry(categories, **changes):
    return {'description': 'Weekly groceries', 'amount': '6850.00', 'merchant': 'Keells', 'transaction_date': '2026-10-05', 'transaction_type': 'expense', 'category_id': categories['Groceries']} | changes

def add(headers, payload):
    response = client.post('/api/transactions', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def upload(headers, text, **options):
    return client.post('/api/imports/preview', headers=headers, files={'file': ('statement.csv', text.encode('utf-8'), 'text/csv')}, data=options)

def test_crud_ownership_search_filters_and_pagination(owners):
    (owner, other), categories = owners
    original = add(owner, entry(categories))
    add(other, entry(categories, description='Private transaction'))
    assert client.get('/api/transactions', headers=other).json()['total'] == 1
    for method in ['get', 'put', 'delete']:
        kwargs = {'json': entry(categories)} if method == 'put' else {}
        assert getattr(client, method)(f"/api/transactions/{original['id']}", headers=other, **kwargs).status_code == 404
    details = client.get(f"/api/transactions/{original['id']}", headers=owner).json()
    assert details['category']['name'] == 'Groceries'
    assert details['source'] == 'manual'
    assert client.post('/api/transactions', headers=owner, json=entry(categories, user_id=999)).status_code == 422
    assert client.post('/api/transactions', headers=owner, json=entry(categories, category_id=categories['Salary'])).status_code == 422
    assert client.post('/api/transactions', headers=owner, json=entry(categories, amount='0')).status_code == 422
    assert client.post('/api/transactions', headers=owner, json=entry(categories, amount='NaN')).status_code == 422
    assert client.post('/api/transactions', headers=owner, json=entry(categories, description=' ')).status_code == 422
    assert client.put(f"/api/transactions/{original['id']}", headers=owner, json=entry(categories, amount='6800.25', merchant='Keells City')).json()['amount'] == '6800.25'
    for index in range(12):
        add(owner, entry(categories, amount=str(index + 1), description=f'Lunch {index}', merchant='Cafe', category_id=categories['Food'], transaction_date='2026-09-30'))
    add(owner, entry(categories, description='Pay day', merchant='Employer', amount='95000', transaction_type='income', category_id=categories['Salary']))
    listing = client.get('/api/transactions?page=2&page_size=5&sort_by=amount&sort_order=asc', headers=owner).json()
    assert listing['total'] == 14 and len(listing['items']) == 5 and listing['pages'] == 3
    assert [float(r['amount']) for r in listing['items']] == sorted(float(r['amount']) for r in listing['items'])
    assert client.get('/api/transactions?search=keells', headers=owner).json()['total'] == 1
    assert client.get('/api/transactions?search=%25', headers=owner).json()['total'] == 0
    assert client.get(f"/api/transactions?category_id={categories['Food']}&date_to=2026-09-30&transaction_type=expense", headers=owner).json()['total'] == 12
    assert client.get('/api/transactions?date_from=2026-10-01&date_to=2026-10-05', headers=owner).json()['total'] == 2
    assert client.get('/api/transactions?transaction_type=income', headers=owner).json()['total'] == 1
    assert client.get('/api/transactions?date_from=2026-10-05&date_to=2026-10-01', headers=owner).status_code == 422
    assert client.get('/api/transactions?sort_by=user_id', headers=owner).status_code == 422
    assert client.get('/api/transactions?page=0', headers=owner).status_code == 422
    assert client.delete(f"/api/transactions/{original['id']}", headers=owner).status_code == 204
    assert client.get(f"/api/transactions/{original['id']}", headers=owner).status_code == 404
    assert client.get('/api/transactions').status_code == 401

def test_dashboard_totals_series_comparison_and_owner_isolation(owners):
    (owner, other), categories = owners
    add(owner, entry(categories))
    add(owner, entry(categories, description='Lunch', amount='12.34', category_id=categories['Food'], transaction_date='2026-10-04'))
    add(owner, entry(categories, description='Salary', amount='95000', category_id=categories['Salary'], transaction_type='income', transaction_date='2026-10-01'))
    add(owner, entry(categories, description='Prior salary', amount='80000', category_id=categories['Salary'], transaction_type='income', transaction_date='2026-09-01'))
    add(owner, entry(categories, description='Prior expense', amount='100', transaction_date='2026-09-02'))
    result = client.get('/api/dashboard?month=2026-10-05', headers=owner).json()
    assert result['month'] == '2026-10-01'
    assert result['income'] == '95000.00' and result['expenses'] == '6862.34' and result['savings'] == '88137.66'
    assert result['previous']['savings'] == '79900.00'
    assert result['changes']['income'] == 18.75
    assert result['changes']['expenses'] == 6762.34
    assert result['top_category'] == 'Groceries'
    assert len(result['monthly']) == 6 and len(result['daily']) == 31
    assert result['daily'][3]['expenses'] == '12.34' and result['daily'][4]['expenses'] == '6850.00'
    assert result['monthly'][0]['income'] == '0.00'
    assert len(result['recent_transactions']) == 3
    empty = client.get('/api/dashboard?month=2026-10-01', headers=other).json()
    assert empty['balance'] == '0.00' and empty['expenses'] == '0.00'
    assert empty['categories'] == [] and empty['recent_transactions'] == [] and empty['changes']['expenses'] is None
    add(other, entry(categories, amount='999999'))
    assert client.get('/api/dashboard?month=2026-10-01', headers=owner).json()['expenses'] == '6862.34'
    assert client.get('/api/dashboard?month=0001-01-01', headers=owner).status_code == 422
    assert client.get('/api/dashboard').status_code == 401

def test_csv_preview_corrections_duplicates_and_idempotent_confirmation(owners):
    (owner, other), categories = owners
    statement = 'Date,Description,Merchant,Debit,Credit\n05/10/2026,Weekly groceries,Keells,"6,850.00",\n05/10/2026,Weekly groceries,Keells,6850,\n01/10/2026,Salary,Employer,,95000\nnot-a-date,Broken,Shop,abc,\n'
    preview = upload(owner, statement).json()
    assert preview['total_rows'] == 4 and preview['valid_rows'] == 3 and preview['invalid_rows'] == 1 and preview['duplicates'] == 1
    assert preview['rows'][0]['transaction']['transaction_date'] == '2026-10-05'
    assert preview['rows'][0]['transaction']['category_id'] == categories['Groceries']
    assert preview['rows'][3]['errors']
    assert client.get('/api/transactions', headers=owner).json()['total'] == 0
    transactions = [row['transaction'] for row in preview['rows'] if not row['errors']]
    body = {'source': 'csv', 'transactions': transactions}
    assert client.post('/api/imports/confirm', headers=owner, json=body).json() == {'imported': 2, 'skipped_duplicates': 1}
    assert client.post('/api/imports/confirm', headers=owner, json=body).json() == {'imported': 0, 'skipped_duplicates': 3}
    assert upload(owner, statement).json()['duplicates'] == 3
    assert upload(other, statement).json()['duplicates'] == 1
    correction = entry(categories, description='Corrected row', amount='23.45', merchant=None)
    assert client.post('/api/imports/confirm', headers=owner, json={'source': 'csv', 'transactions': [correction]}).json()['imported'] == 1
    assert client.post('/api/imports/confirm', headers=owner, json={'source': 'csv', 'transactions': [correction | {'user_id': 999}]}).status_code == 422
    assert client.post('/api/imports/confirm', headers=owner, json={'source': 'csv', 'transactions': [correction | {'category_id': categories['Salary']}]}).status_code == 422
    bad_batch = client.post('/api/imports/confirm', headers=owner, json={'source': 'csv', 'transactions': [correction | {'description': 'Must not save'}, correction | {'amount': '-1'}]})
    assert bad_batch.status_code == 422
    assert client.get('/api/transactions?search=Must%20not%20save', headers=owner).json()['total'] == 0
    assert client.post('/api/imports/confirm', headers=other, json=body).json()['imported'] == 2

def test_custom_mapping_signed_amounts_dates_and_invalid_rows(owners):
    (owner, _), categories = owners
    text = 'When;What;Value\n10/05/2026;Coffee;"Rs. 1,200.50"\n10/06/2026;Refund;500\n2026-10-05;Debit;(250.00)\n2026-10-05;Zero;0\n'
    detected = upload(owner, text).json()
    assert detected['mapping_required'] and detected['columns'] == ['When', 'What', 'Value']
    response = upload(owner, text, mapping='{"transaction_date":"When","description":"What","amount":"Value"}', day_first='false', default_type='income')
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview['rows'][0]['transaction']['transaction_date'] == '2026-10-05'
    assert preview['rows'][0]['transaction']['amount'] == '1200.50'
    assert preview['rows'][0]['transaction']['transaction_type'] == 'income'
    assert preview['rows'][2]['transaction']['transaction_type'] == 'expense'
    assert preview['rows'][3]['errors']
    assert upload(owner, text, mapping='{"transaction_date":"Unknown"}').status_code == 422
    ambiguous = upload(owner, 'Date,Description,Debit,Credit\n05/10/2026,Ambiguous,100,100\n').json()
    assert ambiguous['invalid_rows'] == 1
    precision = upload(owner, 'Date,Description,Amount\n05/10/2026,Precision,12.345\n').json()
    assert precision['invalid_rows'] == 1
    decimal_comma = upload(owner, 'Date;Description;Amount\n05/10/2026;Decimal comma;6.850,00\n').json()
    assert decimal_comma['invalid_rows'] == 1
    foreign_currency = upload(owner, 'Date,Description,Amount\n05/10/2026,Dollars,USD 10\n').json()
    assert foreign_currency['invalid_rows'] == 1

def test_xlsx_upload_validation_and_limits(owners):
    (owner, _), categories = owners
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['Date', 'Description', 'Merchant', 'Debit', 'Credit'])
    sheet.append([datetime(2026, 10, 5), 'Weekly groceries', 'Keells', 6850, None])
    buffer = BytesIO(); workbook.save(buffer)
    response = client.post('/api/imports/preview', headers=owner, files={'file': ('bank.xlsx', buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
    assert response.status_code == 200, response.text
    assert response.json()['source'] == 'xlsx' and response.json()['valid_rows'] == 1
    assert response.json()['rows'][0]['transaction']['transaction_date'] == '2026-10-05'
    assert client.post('/api/imports/preview', headers=owner, files={'file': ('bank.pdf', b'bad', 'application/pdf')}).status_code == 415
    assert client.post('/api/imports/preview', headers=owner, files={'file': ('bank.csv', b'bad', 'image/png')}).status_code == 415
    assert upload(owner, '').status_code == 422
    assert upload(owner, 'Date,Description,Amount\n').status_code == 422
    assert upload(owner, 'Date,Description,Amount\n05/10/2026,Coffee,100,unexpected\n').status_code == 422
    assert client.post('/api/imports/preview', headers=owner, files={'file': ('bank.xlsx', b'not-a-workbook', 'application/octet-stream')}).status_code == 422
    assert client.post('/api/imports/preview', headers=owner, files={'file': ('bank.csv', b'x' * (5 * 1024 * 1024 + 1), 'text/csv')}).status_code == 413
    assert upload(owner, 'Date,Description,Amount\n' + '05/10/2026,Coffee,100\n' * 2001).status_code == 413
    assert client.post('/api/imports/preview', files={'file': ('bank.csv', b'Date,Amount', 'text/csv')}).status_code == 401

def test_concurrent_import_confirmations_do_not_duplicate(owners):
    (owner, _), categories = owners
    body = {'source': 'csv', 'transactions': [entry(categories)]}
    def confirm(_):
        with TestClient(app) as concurrent_client:
            response = concurrent_client.post('/api/imports/confirm', headers=owner, json=body)
            assert response.status_code == 201, response.text
            return response.json()['imported']
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(confirm, range(2))) == [0, 1]
    assert client.get('/api/transactions', headers=owner).json()['total'] == 1
