from datetime import datetime, timedelta, timezone
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
import logging
import re

from models import (
    User, UserCreate, UserUpdate, UserPublic, 
    UserPublicWithLikesAndFollows, BasicResponse,
    PostPublicWithLikes
)
from dependencies import (
    SessionDep, get_current_active_user, get_user,
    get_user_with_follows
)
from services.email import generate_verification_code, send_verification_email
from auth.security import get_password_hash
from core.config import get_settings
from cache import cache_response

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

def is_valid_email(email: str) -> bool:
    """Validate email format using regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

@router.post("", response_model=BasicResponse)
async def create_user(user: UserCreate, session: SessionDep) -> User:
    """Create a new user account"""
    user_db = User.model_validate(user)
    
    # Validate username
    if (not user_db.username.strip()) or user_db.username == "me":
        raise HTTPException(status_code=400, detail="User is not valid")
    
    # Validate password
    if not user_db.password.strip():
        raise HTTPException(status_code=400, detail="Password is not valid")
    
    # Validate email format
    if not is_valid_email(user_db.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    # Check if user exists
    if get_user(user_db.username, session):
        raise HTTPException(status_code=409, detail="User already exists")
    
    # Hash password and generate verification code
    user_db.password = get_password_hash(user_db.password)
    verification_code = generate_verification_code()
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES
    )

    db_user = User(
        username=user_db.username,
        full_name=user_db.full_name,
        email=user_db.email,
        password=user_db.password,
        verification_code=verification_code,
        verification_code_expires=expires,
    )

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    # Send verification email
    if send_verification_email(user_db.email, verification_code):
        return JSONResponse({"message": "User created successfully"})
    else:
        session.delete(db_user)
        session.commit()
        raise HTTPException(status_code=500, detail="Failed to send verification email")

@router.get("/me", response_model=UserPublicWithLikesAndFollows)
@cache_response(settings.CACHE_EXPIRE_TIME)
async def get_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
) -> UserPublicWithLikesAndFollows:
    """Get current user's profile information"""
    return get_user_with_follows(current_user.username, session)

@router.patch("/me", response_model=UserPublic)
async def update_own_user(
    user: UserUpdate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserPublic:
    """Update current user's profile"""
    user_db = User.model_validate(user)
    user_data = user_db.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user

@router.delete("", response_model=BasicResponse)
async def delete_user_me(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Delete current user's account"""
    session.delete(current_user)
    session.commit()
    return JSONResponse({"message": f"User {current_user.username} deleted successfully"})

@router.get("/{username}", response_model=UserPublicWithLikesAndFollows)
@cache_response(settings.CACHE_EXPIRE_TIME)
async def get_user_by_username(username: str, session: SessionDep):
    """Get public profile information for any user"""
    user = get_user_with_follows(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/{username}/posts", response_model=List[PostPublicWithLikes])
async def get_user_posts(username: str, session: SessionDep):
    """Get all posts from a specific user"""
    user = get_user(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.posts

@router.get("/{username}/likes", response_model=List[PostPublicWithLikes])
async def get_user_likes(username: str, session: SessionDep):
    """Get all posts that a specific user has liked"""
    user = get_user(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.likes 