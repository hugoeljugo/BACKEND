from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import select
import logging

from models import User, Post, BasicResponse, UserLink, PostUserLink
from dependencies import SessionDep, get_current_active_user, get_user
from core.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

@router.post("/follow", response_model=BasicResponse)
async def follow_user(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    followed_username: str,
):
    """Follow another user"""
    followed = get_user(followed_username, session)
    if not followed:
        raise HTTPException(status_code=404, detail="User not found")

    existing_link = session.exec(
        select(UserLink).where(
            UserLink.user_id == current_user.id,
            UserLink.following_id == followed.id
        )
    ).first()

    if existing_link:
        raise HTTPException(status_code=400, detail="Already following this user")

    user_link = UserLink(user_id=current_user.id, following_id=followed.id)
    session.add(user_link)
    session.commit()
    return JSONResponse({"message": "User followed successfully"})

@router.delete("/follow", response_model=BasicResponse)
async def unfollow_user(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    unfollowed_username: str,
):
    """Unfollow a user"""
    unfollowed = get_user(unfollowed_username, session)
    if not unfollowed:
        raise HTTPException(status_code=404, detail="User not found")

    existing_link = session.exec(
        select(UserLink).where(
            UserLink.user_id == current_user.id,
            UserLink.following_id == unfollowed.id
        )
    ).first()

    if not existing_link:
        raise HTTPException(status_code=400, detail="Not following this user")

    session.delete(existing_link)
    session.commit()
    return JSONResponse({"message": "User unfollowed successfully"})

@router.post("/like", response_model=BasicResponse)
async def like_post(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    post_id: int,
):
    """Like a post"""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing_link = session.exec(
        select(PostUserLink).where(
            PostUserLink.user_id == current_user.id,
            PostUserLink.post_id == post.id
        )
    ).first()

    if existing_link:
        raise HTTPException(status_code=400, detail="Already liked this post")

    post_user_link = PostUserLink(user_id=current_user.id, post_id=post.id)
    session.add(post_user_link)
    session.commit()
    return JSONResponse({"message": "Post liked successfully"})

@router.delete("/like", response_model=BasicResponse)
async def unlike_post(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    post_id: int,
):
    """Unlike a post"""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing_link = session.exec(
        select(PostUserLink).where(
            PostUserLink.user_id == current_user.id,
            PostUserLink.post_id == post.id
        )
    ).first()

    if not existing_link:
        raise HTTPException(status_code=400, detail="Not liked this post")

    session.delete(existing_link)
    session.commit()
    return JSONResponse({"message": "Post unliked successfully"}) 