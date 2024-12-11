from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4
import logging
from time import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from models.user import UserPublic
from sqlmodel import Session, select, create_engine
from jwt.exceptions import InvalidTokenError
import jwt
from redis import asyncio as aioredis
from sqlmodel import col

from core.config import get_settings
from models import User, TokenData, UserLink
from auth.security import verify_password

settings = get_settings()
logger = logging.getLogger(__name__)
engine = create_engine(settings.DATABASE_URL, echo=True)

# Database dependency
def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

# Authentication dependencies
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_user(username: str, session: Session):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        return False
    return user

def authenticate_user(username: str, password: str, session: Session):
    user = get_user(username, session)
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=15)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user(request: Request, session: SessionDep):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = request.cookies.get("access_token")
        if not token:
            raise credentials_exception
        token = token.replace("Bearer ", "")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    
    user = get_user(username=token_data.username, session=session)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def admin_only(current_user: Annotated[User, Depends(get_current_active_user)]):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Rate limiting dependency
async def rate_limit(key_prefix: str, limit: int, window: int = 60):
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        key = f"rate_limit:{key_prefix}:{int(time() // window)}"

        requests = await redis.incr(key)
        if requests == 1:
            await redis.expire(key, window)

        if requests > limit:
            raise HTTPException(status_code=429, detail="Too many requests")
    except Exception as e:
        logger.error(f"Rate limit error: {str(e)}")
        pass

# Middleware
async def log_requests(request: Request, call_next):
    start_time = time()
    response = await call_next(request)
    process_time = time() - start_time
    
    logger.info(
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Status: {response.status_code} | "
        f"Process Time: {process_time:.2f}s"
    )
    return response

# Error handlers
def setup_error_handlers(app):
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        error_id = str(uuid4())
        logger.error(
            f"Unhandled error {error_id}: {str(exc)}",
            exc_info=True,
            extra={
                "path": request.url.path,
                "method": request.method,
                "error_id": error_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred", "error_id": error_id},
        ) 


def get_user_public(user: User, session: Session) -> UserPublic:
    return UserPublic(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        pfp=user.pfp,
        is_admin=user.is_admin,
        email_verified=user.email_verified,
        two_factor_enabled=user.two_factor_enabled,
        likes=len(user.likes),
        posts=len(user.posts),
        follows=len(list(session.exec(select(UserLink).where(UserLink.user_id == user.id)))),
        followed_by=len(list(session.exec(select(UserLink).where(UserLink.following_id == user.id))))
    )