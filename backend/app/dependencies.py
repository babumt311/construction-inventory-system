"""
Dependencies for FastAPI routes
Re-exports authentication functions from auth.py to avoid circular imports
"""
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status, Query, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, date
import logging

from app.database import get_db
from app import models
from app.auth import (
    get_current_user,
    get_current_active_user,
    has_project_access,
    oauth2_scheme
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
# REPORT FILTER PARAMETERS
# ============================================
class ReportFilterParams:
    def __init__(
        self,
        start_date: Optional[date] = Query(None, description="Start date for reports"),
        end_date: Optional[date] = Query(None, description="End date for reports"),
        project_id: Optional[int] = Query(None, description="Filter by project ID"),
        material_id: Optional[int] = Query(None, description="Filter by material ID"),
        category: Optional[str] = Query(None, description="Filter by category"),
        report_type: Optional[str] = Query(None, description="Type of report"),
        format: str = Query("json", regex="^(json|pdf|csv)$", description="Report format")
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.project_id = project_id
        self.material_id = material_id
        self.category = category
        self.report_type = report_type
        self.format = format


# ============================================
# AUTHENTICATION DEPENDENCIES
# ============================================

async def get_current_user_dependency(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Get current user from token
    """
    return await get_current_user(token, db)


async def get_current_active_user_dependency(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    Get current active user
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def get_admin_user_dependency(
    current_user: models.User = Depends(get_current_active_user)
) -> models.User:
    """
    Require admin role
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires admin role"
        )
    return current_user


def get_owner_or_admin_user_dependency(
    current_user: models.User = Depends(get_current_active_user)
) -> models.User:
    """
    Require owner or admin role
    """
    if current_user.role.value not in ["owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires owner or admin role"
        )
    return current_user


def get_owner_admin_or_manager_dependency(
    current_user: models.User = Depends(get_current_active_user)
) -> models.User:
    """
    Require owner, admin, or manager role
    """
    if current_user.role.value not in ["owner", "admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires owner, admin, or manager role"
        )
    return current_user


# ============================================
# PROJECT ACCESS DEPENDENCIES
# ============================================

def validate_project_access(
    project_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> models.Project:
    """
    Validate that user has access to a project and return the project
    Raises 403 if no access, 404 if project not found
    """
    from app.models import Project
    
    # Get the project
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Admin has access to all projects
    if current_user.role.value == "admin":
        return project
    
    # Owner can access their projects
    if current_user.role.value == "owner":
        # Check if owner owns this project
        if hasattr(project, 'owner_id') and project.owner_id == current_user.id:
            return project
        # Or if there's a many-to-many relationship
        if hasattr(current_user, 'projects'):
            if project in current_user.projects:
                return project
    
    # Regular users can only access assigned projects
    if hasattr(current_user, 'projects'):
        if project in current_user.projects:
            return project
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No access to this project"
    )


def check_project_access(
    project_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> bool:
    """
    Check if user has access to a project
    Returns True/False without raising exception
    """
    try:
        validate_project_access(project_id, current_user, db)
        return True
    except HTTPException:
        return False


# ============================================
# MATERIAL ACCESS DEPENDENCIES
# ============================================

def validate_material_access(
    material_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> models.Material:
    """
    Validate that user has access to a material
    """
    from app.models import Material
    
    material = db.query(Material).filter(Material.id == material_id).first()
    
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    # Admin has access to all materials
    if current_user.role.value == "admin":
        return material
    
    # Check project access if material belongs to a project
    if hasattr(material, 'project_id') and material.project_id:
        validate_project_access(material.project_id, current_user, db)
    
    return material


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
    
    return audit_data


# ============================================
# EXPORT LIST
# ============================================
__all__ = [
    # Pagination
    "PaginationParams",
    "ReportFilterParams",
    
    # Auth dependencies
    "get_current_user",
    "get_current_active_user",
    "get_current_user_dependency",
    "get_current_active_user_dependency",
    "get_admin_user_dependency",
    "get_owner_or_admin_user_dependency",
    "get_owner_admin_or_manager_dependency",
    
    # Access validation
    "validate_project_access",
    "check_project_access",
    "validate_material_access",
    
    # Security
    "verify_user_ownership_or_admin",
    
    # Audit
    "log_audit_action"
]
