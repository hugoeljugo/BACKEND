from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import logging
import re

from sqlmodel import or_, select

from models import (
    User, UserCreate, UserUpdate, UserPublic, 
    BasicResponse, PostPublic, Post
)
from dependencies import (
    SessionDep, get_current_active_user, get_user, add_liked_status, add_followed_status
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

@router.get("/me", response_model=UserPublic)
@cache_response(settings.CACHE_EXPIRE_TIME)
async def get_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
) -> UserPublic:
    """Get current user's profile information"""
    user = get_user(current_user.username, session)
    return user.model_dump()

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

@router.get("/{username}", response_model=UserPublic)
@cache_response(settings.CACHE_EXPIRE_TIME)
async def get_user_by_username(username: str, session: SessionDep, current_user: Annotated[User, Depends(get_current_active_user)]):
    """Get public profile information for any user"""
    user = get_user(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return add_followed_status(user, current_user)

@router.get("/id/{user_id}", response_model=UserPublic)
@cache_response(settings.CACHE_EXPIRE_TIME)
async def get_user_by_id(user_id: int, session: SessionDep):
    """Get public profile information for any user by ID"""
    statement = select(User).where(User.id == user_id)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/search", response_model=List[UserPublic])
async def search_users(
    session: SessionDep,
    query: str = Query(..., min_length=1),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Search users by username or full name"""
    statement = select(User).where(
        or_(
            User.username.ilike(f"%{query}%"),
            User.full_name.ilike(f"%{query}%")
        )
    ).offset(offset).limit(limit)
    users = session.exec(statement).all()
    return users

@router.get("/{username}/stats", response_model=dict)
@cache_response(settings.CACHE_EXPIRE_TIME)
async def get_user_stats(username: str, session: SessionDep):
    """Get user statistics"""
    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "post_count": len(user.posts),
        "likes_received": sum(len(post.liked_by) for post in user.posts),
        "likes_given": len(user.likes),
        "join_date": user.created_at,
    }

@router.get("/{username}/posts", response_model=List[PostPublic])
async def get_user_posts(
    username: str,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """Get all posts from a specific user with pagination and date filtering"""
    statement = select(Post).join(User).where(User.username == username)
    
    if start_date:
        statement = statement.where(Post.date >= start_date)
    if end_date:
        statement = statement.where(Post.date <= end_date)
        
    posts = session.exec(statement.order_by(Post.date.desc()).offset(offset).limit(limit)).all()
    return [add_liked_status(post, current_user) for post in posts]

@router.get("/{username}/likes", response_model=List[PostPublic])
async def get_user_likes(
    username: str, 
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Get all posts that a specific user has liked"""
    user = get_user(username, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return sorted([add_liked_status(post, current_user) for post in user.likes], key=lambda post: post.date, reverse=True)