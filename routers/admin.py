from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.requests import Request
from sqlmodel import select
import logging
from datetime import datetime
import redis

from models import Log, User
from dependencies import SessionDep, admin_only
from core.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name=settings.API_KEY_NAME, auto_error=False)

@router.post("/logs", response_model=Log)
async def create_log(
    request: Request,
    log: Log,
    session: SessionDep,
    current_user: Optional[User] = None,
    api_key: Optional[str] = Security(api_key_header),
) -> Log:
    """Create a log entry. Requires authentication or internal API key."""
    # Allow internal requests without authentication
    if request.client.host == "127.0.0.1":
        is_authorized = True
    else:
        is_authorized = current_user is not None or api_key == settings.API_KEY

    if not is_authorized:
        raise HTTPException(status_code=401, detail="Authentication required")

    db_log = Log(
        level=log.level,
        message=log.message,
        context=log.context,
        user_id=current_user.id if current_user else None,
    )
    session.add(db_log)
    session.commit()
    session.refresh(db_log)
    return db_log

@router.get("/logs")
async def get_logs(
    session: SessionDep,
    current_user: Annotated[User, Depends(admin_only)],
    level: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> List[Log]:
    """Get system logs with optional filters (admin only)"""
    query = select(Log)
    if level:
        query = query.where(Log.level == level)
    if from_date:
        query = query.where(Log.timestamp >= from_date)
    if to_date:
        query = query.where(Log.timestamp <= to_date)
    return session.exec(query).all()

@router.post("/cache/clear")
async def clear_cache(current_user: Annotated[User, Depends(admin_only)]):
    """Clear the Redis cache (admin only)"""
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.flushall()
        logger.info(f"Cache cleared by admin: {current_user.username}")
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Error clearing cache") 