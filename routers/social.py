from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import select
import logging

from models import User, Post, BasicResponse, UserFollow, PostUserLink, Interaction, InteractionType
from dependencies import SessionDep, get_current_active_user, get_user
from core.config import get_settings
from services.engagement import calculate_post_engagement_score, update_user_engagement_rate

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


    existing_link = [follow for follow in current_user.following if follow.id == followed.id]

    if existing_link:
        raise HTTPException(status_code=400, detail="Already following this user")

    # Update counts
    current_user.following_count += 1
    followed.follower_count += 1

    current_user.following.append(followed)
    followed.followers.append(current_user)

    session.add_all([current_user, followed])
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


    existing_link = [follow for follow in current_user.following if follow.id == unfollowed.id]

    if not existing_link:
        raise HTTPException(status_code=400, detail="Not following this user")
    
    # Update counts
    current_user.following_count -= 1
    unfollowed.follower_count -= 1

    current_user.following.remove(unfollowed)

    session.add_all([current_user, unfollowed])
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

    existing_link = [like for like in current_user.likes if like.id == post.id]

    if existing_link:
        raise HTTPException(status_code=400, detail="Already liked this post")

    # Create like interaction
    interaction = Interaction(
        user_id=current_user.id,
        post_id=post.id,
        interaction_type=InteractionType.LIKE
    )
    
    # Update metrics
    post.like_count += 1
    post.engagement_score = calculate_post_engagement_score(post)
    post.user.total_likes_received += 1
    
    # Add records to database
    current_user.likes.append(post)
    post.liked_by.append(current_user)
    session.add_all([current_user, post, interaction])
    session.commit()
    
    # Update user engagement rates
    update_user_engagement_rate(current_user, session)
    update_user_engagement_rate(post.user, session)
    
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

    existing_link = [like for like in current_user.likes if like.id == post.id]

    if not existing_link:
        raise HTTPException(status_code=400, detail="Not liked this post")

    current_user.likes.remove(post)
    session.add_all([current_user, post])
    session.commit()
    return JSONResponse({"message": "Post unliked successfully"}) 