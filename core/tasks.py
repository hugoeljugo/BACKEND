from datetime import datetime, timedelta
from pathlib import Path
import logging
from core.config import get_settings
from sqlmodel import Session, select
from models import Post, User, Interaction, InteractionType
from services.engagement import calculate_post_engagement_score, update_user_engagement_rate

settings = get_settings()
logger = logging.getLogger(__name__)


async def clean_old_files(days: int = 7):
    """
    Delete temporary files older than specified days
    """
    try:
        current_time = datetime.now()
        for file_path in Path(settings.UPLOAD_FOLDER).glob("temp_*"):
            if current_time - datetime.fromtimestamp(file_path.stat().st_mtime) > timedelta(days=days):
                file_path.unlink()
        return {"status": "success", "message": f"Cleaned files older than {days} days"}
    except Exception as e:
        logger.error(f"Error cleaning old files: {str(e)}")
        return {"status": "error", "message": str(e)} 

async def update_engagement_scores(session: Session):
    """Periodically update engagement scores for all posts"""
    try:
        posts = session.exec(select(Post)).all()
        for post in posts:
            post.engagement_score = calculate_post_engagement_score(post)
            session.add(post)
        session.commit()
        
        users = session.exec(select(User)).all()
        for user in users:
            update_user_engagement_rate(user, session)
            
        logger.info("Updated engagement scores successfully")
    except Exception as e:
        logger.error(f"Error updating engagement scores: {str(e)}") 