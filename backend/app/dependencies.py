"""
Dependency injection for the application
"""
from typing import Generator, Optional
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status, Request
import logging
from app.database import SessionLocal, get_db
from app import crud, schemas, models
from app.auth import (
    get_current_user, 
    require_admin, 
    require_owner_or_admin,
    check_project_access
)

logger = logging.getLogger(__name__)

# Database dependency
def get_database() -> Generator:
    """Get database session"""
    logger.debug("Getting database session from dependency")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# User dependencies
def get_current_user_dependency(
    request: Request,
    db: Session = Depends(get_db)
) -> models.User:
    """Dependency to get current user"""
    logger.debug(f"Getting current user for request: {request.method} {request.url.path}")
    return get_current_user(request, db)

def get_current_active_user_dependency(
    current_user: models.User = Depends(get_current_user_dependency)
) -> models.User:
    """Dependency to get current active user"""
    logger.debug(f"Getting current active user: {current_user.username}")
    return current_user

def get_admin_user_dependency(
    current_user: models.User = Depends(get_current_user_dependency)
) -> models.User:
    """Dependency to require admin user"""
    logger.debug(f"Checking admin role for: {current_user.username}")
    return require_admin(current_user)

def get_owner_or_admin_user_dependency(
    current_user: models.User = Depends(get_current_user_dependency)
) -> models.User:
    """Dependency to require owner or admin user"""
    logger.debug(f"Checking owner/admin role for: {current_user.username}")
    return require_owner_or_admin(current_user)

# Project access dependency
def validate_project_access(
    project_id: int,
    current_user: models.User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """Dependency to validate user has access to project"""
    logger.debug(f"Validating project access for user {current_user.id} to project {project_id}")
    check_project_access(current_user, project_id, db)
    return project_id

# Pagination dependency
class PaginationParams:
    """Dependency for pagination parameters"""
    
    def __init__(
        self,
        page: int = 1,
        size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "asc"
    ):
        self.page = max(1, page)
        self.size = max(1, min(size, 100))  # Limit to 100 per page
        self.skip = (self.page - 1) * self.size
        self.sort_by = sort_by
        self.sort_order = sort_order
        
        logger.debug(f"Pagination params: page={self.page}, size={self.size}, sort_by={self.sort_by}")

# Report filter dependency
class ReportFilterParams:
    """Dependency for report filtering parameters"""
    
    def __init__(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        project_id: Optional[int] = None,
        site_id: Optional[int] = None,
        material_id: Optional[int] = None,
        supplier_name: Optional[str] = None,
        category_id: Optional[int] = None
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.project_id = project_id
        self.site_id = site_id
        self.material_id = material_id
        self.supplier_name = supplier_name
        self.category_id = category_id
        
        logger.debug(f"Report filter params: project_id={self.project_id}, start_date={self.start_date}")

# Audit logging dependency
def log_audit_action(
    request: Request,
    current_user: models.User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
    action: Optional[str] = None,
    table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    old_values: Optional[str] = None,
    new_values: Optional[str] = None
):
    """Dependency to log audit actions"""
    
    # Extract client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Default values from request
    if not action:
        action = request.method
    if not table_name:
        # Extract table name from URL path
        path_parts = request.url.path.strip("/").split("/")
        if len(path_parts) > 0:
            table_name = path_parts[0]
    
    # Log the action
    if table_name and action in ["POST", "PUT", "PATCH", "DELETE"]:
        logger.info(f"Audit logging: {action} on {table_name} by {current_user.username}")
        
        crud.crud_audit_log.log_action(
            db=db,
            user_id=current_user.id,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    return {
        "logged": True,
        "user_id": current_user.id,
        "action": action,
        "table_name": table_name
    }

# CLI Output helper for dependencies
def cli_dependency_info():
    """CLI output for dependency information"""
    print("🔧 Dependencies initialized:")
    print("  ✅ Database session management")
    print("  ✅ User authentication and authorization")
    print("  ✅ Role-based access control (RBAC)")
    print("  ✅ Project access validation")
    print("  ✅ Pagination support")
    print("  ✅ Report filtering")
    print("  ✅ Audit logging")
