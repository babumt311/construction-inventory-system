from sqlalchemy.orm import Session
from app.models import ActivityLog
import logging

logger = logging.getLogger(__name__)

def log_activity(db: Session, user_name: str, action: str, details: str = None):
    """Universal function to record user actions into the database."""
    try:
        new_log = ActivityLog(
            user_name=user_name,
            action=action,
            details=details
        )
        db.add(new_log)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save activity log: {str(e)}")
