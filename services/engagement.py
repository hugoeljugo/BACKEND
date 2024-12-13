from datetime import datetime, timezone
from sqlmodel import Session, select
from models import Post, User, Interaction, InteractionType

def calculate_post_engagement_score(post: Post) -> float:
    """Calculate engagement score for a post"""
    weights = {
        'like': 1.0,
        'reply': 1.2,
        'share': 1.5,
        'view': 0.1
    }
    
    total_score = (
        post.like_count * weights['like'] +
        post.reply_count * weights['reply'] +
        post.share_count * weights['share'] +
        post.view_count * weights['view']
    )
    
    hours_since_post = (datetime.now(timezone.utc) - post.date.replace(tzinfo=timezone.utc)).total_seconds() / 3600
    time_decay = 1 / (1 + hours_since_post/24)  # 24-hour half-life
    
    return total_score * time_decay

def update_user_engagement_rate(user: User, session: Session) -> float:
    """Calculate and update user's engagement rate"""
    total_interactions = session.exec(
        select(Interaction).where(Interaction.user_id == user.id)
    ).all()
    
    # Calculate engagement rate based on interactions per post
    if user.post_count > 0:
        engagement_rate = len(total_interactions) / user.post_count
    else:
        engagement_rate = 0.0
    
    user.engagement_rate = engagement_rate
    session.add(user)
    session.commit()
    
    return engagement_rate 