from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel import select
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import Float, case, func, select as sa_select, cast

from models import User, Post, PostCreate, PostPublic, Interaction, InteractionType, PostUserLink, Topic
from dependencies import SessionDep, get_current_active_user, rate_limit, add_liked_status
from core.config import get_settings
from cache import cache_response
from services.engagement import calculate_post_engagement_score, update_user_engagement_rate

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
    
    # Initialize engagement metrics
    post_db.view_count = 0
    post_db.like_count = 0
    post_db.reply_count = 0
    post_db.share_count = 0
    post_db.engagement_score = 0.0
    
    # Update user metrics
    current_user.post_count += 1
    
    session.add(post_db)
    session.commit()
    session.refresh(post_db)
    
    return post_db

@router.get("/me", response_model=List[PostPublic])
async def get_own_posts(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
):
    """Get all posts created by the current user"""
    return current_user.posts


@router.get("/feed", response_model=List[PostPublic])
@cache_response(settings.CACHE_EXPIRE_TIME)
async def get_posts_feed(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    """Get personalized post feed"""
    try:
        offset = (page - 1) * limit
        
        # Get user's interested topics and following list
        user_topic_ids = [t.id for t in current_user.interested_topics]
        following_ids = [u.id for u in current_user.following]
        
        base_query = select(Post).join(User).where(
            Post.parent_id == None  # Only get top-level posts
        ).order_by(
            (
                # Post engagement (25%)
                Post.engagement_score * 0.25 +
                
                # Author credibility (15%)
                (User.engagement_rate * 0.07 +
                 case(
                     (User.is_verified == True, 0.04),
                     else_=0.0
                 ) +
                 case(
                     (User.follower_count / 100.0 > 0.04, 0.04),
                     else_=func.least(User.follower_count / 100.0, 0.04)
                 )) +
                
                # Author activity (10%)
                cast(func.extract('epoch', User.last_active), Float) / 
                cast(func.extract('epoch', func.now()), Float) * 0.1 +
                
                # Content freshness (30%)
                case(
                    (cast(func.extract('epoch', func.now() - Post.date), Float) / 86400 > 1, 0),
                    else_=1.0 - cast(func.extract('epoch', func.now() - Post.date), Float) / 86400
                ) * 0.3 +
                
                # Topic relevance (10%)
                case(
                    (Post.topics.any(Topic.id.in_(user_topic_ids)), 0.1),
                    else_=0
                ) +
                
                # Social graph relevance (5%)
                case(
                    (Post.user_id.in_(following_ids), 0.05),
                    else_=0
                ) +
                
                # Interaction history (5%)
                case(
                    (Post.user_id.in_(
                        sa_select(Post.user_id)
                        .join(PostUserLink)
                        .where(PostUserLink.user_id == current_user.id)
                        .group_by(Post.user_id)
                        .having(func.count() > 0)
                    ), 0.05),
                    else_=0
                )
            ).desc()
        )
        
        posts = session.exec(base_query.offset(offset).limit(limit)).all()
        return [add_liked_status(post, current_user) for post in posts]
        
    except Exception as e:
        logger.error(f"Error in get_posts_feed: {str(e)}")
        if session.in_transaction():
            session.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while fetching the feed"
        )

@router.get("/{post_id}", response_model=PostPublic)
async def get_post(
    post_id: int,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)] = None
) -> PostPublic:
    """Get a specific post by ID"""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    # Track view if user is authenticated
    if current_user and current_user.id != post.user_id:
        try:
            await track_post_view(post_id, session, current_user)
        except Exception as e:
            logger.error(f"Failed to track view for post {post_id}: {e}")
            
    return add_liked_status(post, current_user)

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


@router.post("/{post_id}/view")
async def track_post_view(
    post_id: int,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Track a post view"""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    # Don't count self-views
    if post.user_id == current_user.id:
        return JSONResponse({"message": "View recorded"})
        
    interaction = Interaction(
        user_id=current_user.id,
        post_id=post.id,
        interaction_type=InteractionType.VIEW
    )
    
    # Update view counts and engagement metrics
    post.view_count += 1
    post.engagement_score = calculate_post_engagement_score(post)
    post.user.total_views_received += 1
    
    session.add_all([interaction, post])
    session.commit()
    
    # Update engagement rate asynchronously
    update_user_engagement_rate(post.user, session)
    
    return JSONResponse({"message": "View recorded"})