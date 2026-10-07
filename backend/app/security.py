from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User

password_hash = PasswordHash.recommended()
dummy_hash = password_hash.hash('dummy-password-for-timing')
bearer = HTTPBearer(auto_error=False)

def create_token(user_id: int):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user_id), 'iat': now, 'exp': now + timedelta(minutes=settings.access_token_minutes)}, settings.jwt_secret, algorithm='HS256')

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    error = HTTPException(401, 'Please sign in again', headers={'WWW-Authenticate': 'Bearer'})
    if credentials is None:
        raise error
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=['HS256'], options={'require': ['sub', 'iat', 'exp']})
        user = db.get(User, int(payload['sub']))
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise error
    if user is None:
        raise error
    return user
