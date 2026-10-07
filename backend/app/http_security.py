"""Shared PostgreSQL limits; never trust forwarded headers or log financial payloads."""
import hashlib
import hmac
import time
from datetime import datetime, timezone, timedelta
import jwt
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from .database import SessionLocal
from .models import RateLimitBucket
from .config import settings

def consume(identity,group,limit,seconds,now=None):
    now=now if now is not None else time.time()
    window=int(now)//seconds
    key=hmac.new(settings.jwt_secret.encode(),f'{identity}:{group}:{window}'.encode(),hashlib.sha256).hexdigest()
    expires=datetime.fromtimestamp((window+1)*seconds,timezone.utc)
    with SessionLocal() as db:
        statement=insert(RateLimitBucket).values(key=key,count=1,expires_at=expires)
        count=db.scalar(statement.on_conflict_do_update(index_elements=['key'],set_={'count':RateLimitBucket.count+1}).returning(RateLimitBucket.count))
        # Expired buckets are disposable, without retaining IPs or token data.
        db.execute(delete(RateLimitBucket).where(RateLimitBucket.expires_at<datetime.fromtimestamp(now,timezone.utc)-timedelta(minutes=1)))
        db.commit()
    return count<=limit,max(1,int(expires.timestamp()-now))

def limits(request):
    ip=request.client.host if request.client else 'unknown'
    identity='ip:'+ip
    token=request.headers.get('authorization','')
    if token.startswith('Bearer '):
        try:
            payload=jwt.decode(token[7:],settings.jwt_secret,algorithms=['HS256'],options={'require':['sub','exp','iat']})
            identity='user:'+str(int(payload['sub']))
        except (jwt.InvalidTokenError,ValueError,TypeError):pass
    path=request.url.path
    if path in ('/api/auth/login','/api/auth/register'):
        return [('ip:'+ip,'auth',settings.auth_rate_limit,60)]
    result=[('ip:'+ip,'requests',settings.api_rate_limit,60)]
    if path.startswith('/api/ai/') or (path=='/api/reports' and request.method=='POST') or path.endswith('/train-category-model') or path.endswith('/unusual/scan'):
        result.append((identity,'analysis',settings.analysis_rate_limit,60))
    return result

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        if request.url.path.startswith('/api/') and request.method!='OPTIONS' and request.url.path!='/api/health':
            try:
                for identity,group,limit,seconds in limits(request):
                    allowed,retry=await run_in_threadpool(consume,identity,group,limit,seconds)
                    if not allowed:
                        return self.headers(JSONResponse({'detail':'Too many requests. Please try again shortly.'},429,headers={'Retry-After':str(retry)}))
            except Exception:
                return self.headers(JSONResponse({'detail':'Security service unavailable. Please try again shortly.'},503))
            if request.method in ('POST','PUT','PATCH'):
                maximum=6*1024*1024 if request.url.path.startswith('/api/imports/') else 256*1024
                length=request.headers.get('content-length')
                if length:
                    try:
                        if int(length)<0:raise ValueError()
                        if int(length)>maximum:return self.headers(JSONResponse({'detail':'Request body is too large.'},413))
                    except ValueError:return self.headers(JSONResponse({'detail':'Invalid content length.'},400))
                chunks=[];size=0
                async for chunk in request.stream():
                    size+=len(chunk)
                    if size>maximum:return self.headers(JSONResponse({'detail':'Request body is too large.'},413))
                    chunks.append(chunk)
                request._body=b''.join(chunks)
        response=await call_next(request)
        return self.headers(response)

    @staticmethod
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store'
        return response
