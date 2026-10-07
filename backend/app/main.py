import logging
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Category, User
from .schemas import CategoryRead, LoginRequest, RegisterRequest, TokenResponse, UserRead
from .security import create_token, current_user, dummy_hash, password_hash
from .transactions import router as transactions_router
from .dashboard import router as dashboard_router
from .imports import router as imports_router
from .intelligence.routes import router as intelligence_router
from .financial_ai import router as ai_router
from .goals import router as goals_router

app = FastAPI(title='LifeLens AI', version='0.3.0')
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=False, allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])
app.include_router(transactions_router)
app.include_router(dashboard_router)
app.include_router(imports_router)
app.include_router(intelligence_router)
app.include_router(ai_router)
app.include_router(goals_router)

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Never echo submitted passwords or other raw request data in validation errors.
    errors = [{'loc': list(error['loc']), 'msg': error['msg'], 'type': error['type']} for error in exc.errors()]
    return JSONResponse(status_code=422, content={'detail': errors})

@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logging.getLogger(__name__).error('Database operation failed', exc_info=exc)
    return JSONResponse(status_code=503, content={'detail': 'Database unavailable. Please try again shortly.'})

@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logging.getLogger(__name__).error('Unexpected error', exc_info=exc)
    return JSONResponse(status_code=500, content={'detail': 'An unexpected error occurred.'})

@app.get('/api/health')
def health(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status': 'ok', 'database': 'connected'}

@app.post('/api/auth/register', response_model=UserRead, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = str(body.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, 'An account with this email already exists')
    user = User(name=body.name, email=email, password_hash=password_hash.hash(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'An account with this email already exists')
    db.refresh(user)
    return user

@app.post('/api/auth/login', response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    valid = password_hash.verify(body.password, user.password_hash if user else dummy_hash)
    if not user or not valid:
        raise HTTPException(401, 'Invalid email or password', headers={'WWW-Authenticate': 'Bearer'})
    return TokenResponse(access_token=create_token(user.id))

@app.get('/api/auth/me', response_model=UserRead)
def me(user: User = Depends(current_user)):
    return user

@app.get('/api/categories', response_model=list[CategoryRead])
def categories(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Category).order_by(Category.id)).all()
