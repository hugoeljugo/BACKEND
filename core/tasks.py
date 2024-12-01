from datetime import datetime, timedelta
from pathlib import Path
import logging
from core.config import get_settings

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