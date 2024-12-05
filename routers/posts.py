from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel import select
import logging

from models import User, Post, PostCreate, PostPublic, PostPublicWithLikes
from dependencies import SessionDep, get_current_active_user, rate_limit
from core.config import get_settings
from cache import cache_response

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

@router.post(
    "",
    response_model=PostPublic,
    dependencies=[Depends(lambda: rate_limit("posts", settings.POSTS_PER_MINUTE).__await__())]
)
async def create_post(
    post: PostCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PostPublic:
    """Create a new post"""
    post_db = Post.model_validate(post)
    post_db.user_id = current_user.id
    session.add(post_db)
    session.commit()
    session.refresh(post_db)
    return post_db

@router.get("/me", response_model=List[PostPublicWithLikes])
async def get_own_posts(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
):
    """Get all posts created by the current user"""
    return current_user.posts

@router.get("/{post_id}", response_model=PostPublicWithLikes)
async def get_post(post_id: int, session: SessionDep) -> PostPublicWithLikes:
    """Get a specific post by ID"""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.delete("/{post_id}", response_model=PostPublic)
async def delete_post(
    post_id: int,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PostPublic:
    """Delete a specific post"""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.user_id != current_user.id:
        raise HTTPException(status_code=401, detail="Not authorized to delete this post")
    session.delete(post)
    session.commit()
    return post

@router.get("/feed", response_model=List[PostPublicWithLikes])
@cache_response(settings.CACHE_EXPIRE_TIME)
async def get_posts_feed(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    """Get paginated post feed"""
    offset = (page - 1) * limit
    posts = session.exec(
        select(Post).order_by(Post.date.desc()).offset(offset).limit(limit)
    ).all()
    return posts 