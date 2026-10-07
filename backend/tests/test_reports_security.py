from datetime import date, datetime, timezone, timedelta
from io import BytesIO
import json
import uuid
import jwt
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import delete
from pydantic import SecretStr
from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models import User, RateLimitBucket
from app.seed import seed
from app.http_security import consume
from app import reports

client=TestClient(app)

@pytest.fixture
def accounts(monkeypatch):
    monkeypatch.setattr(settings,'openai_api_key',SecretStr(''))
    monkeypatch.setattr(reports,'today',lambda:date(2026,10,7))
    seed();users=[]
    for _ in range(2):
        email='report-'+uuid.uuid4().hex+'@example.com'
        user=client.post('/api/auth/register',json={'name':'Report Test','email':email,'password':'report-test-password'}).json()
        token=client.post('/api/auth/login',json={'email':email,'password':'report-test-password'}).json()['access_token']
        users.append((user['id'],{'Authorization':'Bearer '+token}))
    yield users
    with SessionLocal() as db:
        db.execute(delete(User).where(User.id.in_([u[0] for u in users])));db.commit()

def add(headers,category,amount,direction,day):
    response=client.post('/api/transactions',headers=headers,json={'description':'Report fixture','amount':amount,'transaction_type':direction,'transaction_date':day,'category_id':category})
    assert response.status_code==201,response.text
    return response.json()

def test_report_data_pdf_history_snapshot_and_ownership(accounts):
    (_,owner),(_,other)=accounts
    categories={c['name']:c['id'] for c in client.get('/api/categories',headers=owner).json()}
    add(owner,categories['Salary'],'95000','income','2026-09-01')
    expense=add(owner,categories['Food'],'51200','expense','2026-09-05')
    add(other,categories['Food'],'999999','expense','2026-09-06')
    data=client.get('/api/reports/data?month=2026-09-01',headers=owner).json()
    assert data['income']=='95000.00' and data['expenses']=='51200.00'
    assert data['savings']=='43800.00' and data['savings_rate']==46.1 and not data['partial']
    assert data['forecast']['target_month']=='2026-10-01'
    response=client.post('/api/reports',headers=owner,json={'month':'2026-09-01'})
    assert response.status_code==201,response.text
    report=response.json()
    assert len(client.get('/api/reports',headers=owner).json()['items'])==1
    assert client.get('/api/reports',headers=other).json()['items']==[]
    for suffix in ('','/pdf'):
        assert client.get(f"/api/reports/{report['id']}"+suffix,headers=other).status_code==404
    assert client.delete(f"/api/reports/{report['id']}",headers=other).status_code==404
    assert client.delete('/api/transactions/'+str(expense['id']),headers=owner).status_code==204
    assert client.get(f"/api/reports/{report['id']}",headers=owner).json()['data']['expenses']=='51200.00'
    pdf=client.get(f"/api/reports/{report['id']}/pdf",headers=owner)
    assert pdf.content.startswith(b'%PDF') and pdf.headers['content-type']=='application/pdf'
    assert 'attachment;' in pdf.headers['content-disposition']
    reader=PdfReader(BytesIO(pdf.content))
    text=' '.join(page.extract_text() for page in reader.pages)
    for value in ('Monthly Financial Report','September 2026','95,000.00','51,200.00','43,800.00','46.1%','Six-month financial trend','Unusual spending','Local financial analysis'):
        assert value in text
    assert len(reader.pages)>=2
    assert client.delete(f"/api/reports/{report['id']}",headers=owner).status_code==204
    assert client.get(f"/api/reports/{report['id']}",headers=owner).status_code==404

def test_report_empty_partial_validation_and_auth(accounts):
    (_,owner),_=accounts
    data=client.get('/api/reports/data?month=2026-10-01',headers=owner).json()
    assert data['partial'] and data['savings_rate'] is None and data['categories']==[]
    assert client.get('/api/reports/data?month=2026-11-01',headers=owner).status_code==422
    assert client.get('/api/reports/data?month=0001-01-01',headers=owner).status_code==422
    assert client.get('/api/reports').status_code==401
    assert client.post('/api/reports',headers=owner,json={'month':'invalid'}).status_code==422

def test_shared_rate_limit_window():
    identity='test-'+uuid.uuid4().hex
    assert consume(identity,'test',2,60,10000)[0]
    assert consume(identity,'test',2,60,10000)[0]
    allowed,retry=consume(identity,'test',2,60,10000)
    assert not allowed and 0<retry<=60
    assert consume(identity,'test',2,60,10080)[0]

def test_http_rate_limit_and_forwarded_header_ignored(monkeypatch):
    monkeypatch.setattr(settings,'auth_rate_limit',1)
    isolated=TestClient(app,client=('rate-'+uuid.uuid4().hex,5000))
    body={'email':'none@example.com','password':'incorrect'}
    assert isolated.post('/api/auth/login',json=body).status_code==401
    blocked=isolated.post('/api/auth/login',json=body,headers={'X-Forwarded-For':'9.9.9.9'})
    assert blocked.status_code==429 and int(blocked.headers['retry-after'])>0

def test_size_limit_chunked_security_headers_and_cors():
    response=client.post('/api/auth/login',content=b'x'*(256*1024+1),headers={'Content-Type':'application/json'})
    assert response.status_code==413
    chunked=client.post('/api/auth/login',content=iter([b'x'*(128*1024)]*3),headers={'Content-Type':'application/json'})
    assert chunked.status_code==413
    health=client.get('/api/health')
    assert health.headers['x-content-type-options']=='nosniff'
    assert health.headers['cache-control']=='no-store'
    for origin,allowed in [(settings.frontend_origin,True),('https://untrusted.example',False)]:
        result=client.options('/api/auth/login',headers={'Origin':origin,'Access-Control-Request-Method':'POST'})
        assert ('access-control-allow-origin' in result.headers)==allowed

def test_expired_token_and_sql_search_is_literal(accounts):
    (user_id,owner),_=accounts
    now=datetime.now(timezone.utc)
    token=jwt.encode({'sub':str(user_id),'iat':now-timedelta(hours=2),'exp':now-timedelta(hours=1)},settings.jwt_secret,algorithm='HS256')
    assert client.get('/api/reports',headers={'Authorization':'Bearer '+token}).status_code==401
    response=client.get("/api/transactions",params={'search':"' OR 1=1; DROP TABLE users; --"},headers=owner)
    assert response.status_code==200 and response.json()['total']==0
    assert client.get('/api/auth/me',headers=owner).status_code==200
