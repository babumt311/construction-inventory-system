"""
Authentication router for user login and token management
"""
from app.auth import check_project_access
from app.auth import get_admin_user_dependency
from datetime import timedelta, datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import logging
from app import schemas, crud, models
from app.auth import authenticate_user, create_access_token, get_current_user
from app.database import get_db
from app.config import settings
from app.dependencies import log_audit_action
from app.utils.logger import log_activity

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)

@router.post("/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    audit_log: dict = Depends(lambda: {"action": "LOGIN"})
) -> Any:
    logger.info(f"Login attempt for username: {form_data.username}")
    
    user = authenticate_user(db, form_data.username, form_data.password)

    user.last_login = datetime.now()
    db.commit()
    
    if not user:
        logger.warning(f"Failed login attempt for: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        logger.warning(f"Inactive user login attempt: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    logger.info(f"Successful login for user: {user.username}")
    
    # SYSTEM LOGGING
    log_activity(db, user.username, "Login", "User successfully logged into the system.")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/refresh", response_model=schemas.Token)
async def refresh_token(
    current_user: models.User = Depends(get_current_user),
    audit_log: dict = Depends(lambda: {"action": "REFRESH_TOKEN"})
) -> Any:
    logger.info(f"Token refresh requested for user: {current_user.username}")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.username, "user_id": current_user.id, "role": current_user.role.value},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": current_user
    }

@router.get("/me", response_model=schemas.UserInDB)
async def read_users_me(
    current_user: models.User = Depends(get_current_user)
) -> Any:
    return current_user

@router.post("/logout")
async def logout(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    audit_log: dict = Depends(lambda: {"action": "LOGOUT"})
) -> Any:
    logger.info(f"User logout: {current_user.username}")
    # SYSTEM LOGGING
    log_activity(db, current_user.username, "Logout", "User logged out of the system.")
    return {"message": "Successfully logged out"}

@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    audit_log: dict = Depends(lambda: {"action": "CHANGE_PASSWORD"})
) -> Any:
    from app.auth import verify_password, get_password_hash
    
    if not verify_password(old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password"
        )
    
    current_user.hashed_password = get_password_hash(new_password)
    db.add(current_user)
    db.commit()
    
    # SYSTEM LOGGING
    log_activity(db, current_user.username, "Password Change", "User changed their account password.")
    
    return {"message": "Password changed successfully"}

# NEW: ACTIVITY LOGS ENDPOINT FOR DASHBOARD
@router.get("/activity-logs")
def get_recent_activities(db: Session = Depends(get_db), limit: int = 20):
    """Fetch the most recent system activities for the dashboard."""
    logs = db.query(models.ActivityLog).order_by(models.ActivityLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": log.id,
            "user_name": log.user_name,
            "action": log.action,
            "details": log.details,
            "created_at": log.created_at
        } for log in logs
    ]
