"""
User management router
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging
from app import schemas, crud, models
from app.database import get_db
from app.dependencies import (
    get_admin_user_dependency,
    get_owner_or_admin_user_dependency,
    get_current_user_dependency,
    verify_user_ownership_or_admin,  # <-- Added the new security dependency here
    PaginationParams,
    log_audit_action
)

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)


# ============================================
# ADD THIS STATS ENDPOINT - FIXES THE 422 ERROR
# ============================================
@router.get("/stats")
async def get_user_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency)
) -> Any:
    """
    Get user statistics (Owner/Admin only)
    Returns counts for total users, admins, and owners
    """
    logger.info(f"Fetching user stats by: {current_user.username}")
    
    try:
        # Get total users count
        total_users = db.query(models.User).count()
        
        # Get admin users count
        admins = db.query(models.User).filter(
            models.User.role == schemas.UserRole.ADMIN
        ).count()
        
        # Get owner users count
        owners = db.query(models.User).filter(
            models.User.role == schemas.UserRole.OWNER
        ).count()
        
        logger.info(f"Stats: total_users={total_users}, admins={admins}, owners={owners}")
        
        return {
            "total_users": total_users,
            "admins": admins,
            "owners": owners,
            "active_projects": 0  # Placeholder - can be updated later
        }
        
    except Exception as e:
        logger.error(f"Error fetching user stats: {str(e)}")
        # Return default values on error
        return {
            "total_users": 0,
            "admins": 0,
            "owners": 0,
            "active_projects": 0
        }


@router.post("/", response_model=schemas.UserInDB)
async def create_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Create new user (Admin only)
    """
    logger.info(f"Creating new user: {user_in.username} by admin: {current_user.username}")
    
    # Check if user already exists
    db_user = crud.crud_user.get_by_username(db, username=user_in.username)
    if db_user:
        logger.warning(f"Username already exists: {user_in.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    db_user = crud.crud_user.get_by_email(db, email=user_in.email)
    if db_user:
        logger.warning(f"Email already exists: {user_in.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user = crud.crud_user.create(db, obj_in=user_in)
    
    logger.info(f"User created successfully: {user.username} (ID: {user.id})")
    
    return user


@router.get("/", response_model=List[schemas.UserInDB])
async def read_users(
    pagination: PaginationParams = Depends(),
    role: Optional[schemas.UserRole] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency) # Kept the original here for the list view
) -> Any:
    """
    Retrieve users (Owner/Admin only)
    """
    logger.debug(f"Reading users list by: {current_user.username}")
    
    query = db.query(models.User)
    
    # Apply filters
    if role:
        query = query.filter(models.User.role == role)
    
    if active_only:
        query = query.filter(models.User.is_active == True)
    
    # Apply sorting
    if pagination.sort_by:
        if hasattr(models.User, pagination.sort_by):
            if pagination.sort_order == "desc":
                query = query.order_by(getattr(models.User, pagination.sort_by).desc())
            else:
                query = query.order_by(getattr(models.User, pagination.sort_by).asc())
    
    # Apply pagination
    users = query.offset(pagination.skip).limit(pagination.size).all()
    
    logger.debug(f"Returning {len(users)} users")
    return users


@router.get("/{user_id}", response_model=schemas.UserWithProjects)
async def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    # Swapped dependency below to fix IDOR
    current_user: models.User = Depends(verify_user_ownership_or_admin) 
) -> Any:
    """
    Get user by ID (Owner/Admin only)
    """
    logger.debug(f"Reading user ID: {user_id} by: {current_user.username}")
    
    user = crud.crud_user.get(db, id=user_id)
    
    if not user:
        logger.warning(f"User not found: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.put("/{user_id}", response_model=schemas.UserInDB)
async def update_user(
    user_id: int,
    user_in: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Update user (Admin only)
    """
    logger.info(f"Updating user ID: {user_id} by admin: {current_user.username}")
    
    user = crud.crud_user.get(db, id=user_id)
    
    if not user:
        logger.warning(f"User not found for update: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from demoting themselves
    if user.id == current_user.id and user_in.role and user_in.role != schemas.UserRole.ADMIN:
        logger.warning(f"Admin {current_user.username} attempted to demote themselves")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role from admin"
        )
    
    # Check for duplicate email/username if changing
    if user_in.email and user_in.email != user.email:
        db_user = crud.crud_user.get_by_email(db, email=user_in.email)
        if db_user:
            logger.warning(f"Email already exists: {user_in.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    if user_in.username and user_in.username != user.username:
        db_user = crud.crud_user.get_by_username(db, username=user_in.username)
        if db_user:
            logger.warning(f"Username already exists: {user_in.username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
    
    updated_user = crud.crud_user.update(db, db_obj=user, obj_in=user_in)
    
    logger.info(f"User updated successfully: {updated_user.username}")
    
    return updated_user


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Delete user (Admin only)
    """
    logger.info(f"Deleting user ID: {user_id} by admin: {current_user.username}")
    
    # Prevent self-deletion
    if user_id == current_user.id:
        logger.warning(f"Admin {current_user.username} attempted to delete themselves")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # FIX: Fetch the user FIRST before attempting to delete
    user = crud.crud_user.get(db, id=user_id)
    
    if not user:
        logger.warning(f"User not found for deletion: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    crud.crud_user.delete(db, id=user_id)
    
    logger.info(f"User deleted successfully: ID {user_id}")
    
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Activate user account (Admin only)
    """
    logger.info(f"Activating user ID: {user_id} by admin: {current_user.username}")
    
    user = crud.crud_user.get(db, id=user_id)
    
    if not user:
        logger.warning(f"User not found for activation: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # FIX: Use standard CRUD operations instead of raw db commands
    user_in = schemas.UserUpdate(is_active=True)
    user = crud.crud_user.update(db, db_obj=user, obj_in=user_in)
    
    logger.info(f"User activated: {user.username}")
    
    return {"message": "User activated successfully"}
