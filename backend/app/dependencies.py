"""
Dependencies for FastAPI routes
Re-exports authentication functions from auth.py to avoid circular imports
"""
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from app.database import get_db
from app import models
from app.auth import (
    get_current_user,
    get_current_active_user,
    get_admin_user_dependency,
    require_owner_or_admin,
    check_project_access as auth_check_project_access
)

logger = logging.getLogger(__name__)


# ============================================
# PAGINATION PARAMETERS
# ============================================
class PaginationParams:
    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        size: int = Query(100, ge=1, le=1000, description="Number of records to return"),
        sort_by: Optional[str] = Query(None, description="Field to sort by"),
        sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order")
    ):
        self.skip = skip
        self.size = size
        self.sort_by = sort_by
        self.sort_order = sort_order


# ============================================
# AUTHENTICATION DEPENDENCIES (Re-exported from auth.py)
# ============================================
# Re-export these so other files can import from dependencies.py
def get_owner_or_admin_user_dependency(
    current_user: models.User = Depends(get_current_active_user)
) -> models.User:
    """
    Require owner or admin role
    Re-exported from auth.require_owner_or_admin
    """
    return require_owner_or_admin(current_user)


def check_project_access(
    project_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> bool:
    """
    Check if user has access to a project
    Raises HTTPException if no access
    """
    return auth_check_project_access(current_user, project_id, db)


# ============================================
# IDOR PREVENTION DEPENDENCY
# ============================================
async def verify_user_ownership_or_admin(
    user_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Verify that the current user owns the requested resource or is admin
    Used for IDOR prevention
    """
    # Admin can access any user
    if current_user.role.value == "admin":
        return current_user
    
    # Regular users can only access their own data
    if current_user.id == user_id:
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this resource"
    )


# ============================================
# AUDIT LOG DEPENDENCY
# ============================================
async def log_audit_action(
    request: Request,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Log user actions for audit trail
    """
    audit_data = {
        "user_id": current_user.id,
        "username": current_user.username,
        "timestamp": datetime.utcnow(),
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host if request.client else None,
    }
    
    logger.info(f"Audit: {audit_data}")
    
    # You can optionally store this in a database table
    # audit_log = models.AuditLog(**audit_data)
    # db.add(audit_log)
    # db.commit()
    
    return audit_data


# ============================================
# EXPORT LIST
# ============================================
__all__ = [
    "PaginationParams",
    "get_current_user",
    "get_current_active_user",
    "get_admin_user_dependency",
    "get_owner_or_admin_user_dependency",
    "verify_user_ownership_or_admin",
    "check_project_access",
    "log_audit_action"
]
