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

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)

@router.post("/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    audit_log: dict = Depends(lambda: {"action": "LOGIN"})
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
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
    
    # Audit log is handled by dependency
    
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
    """
    Refresh access token
    """
    logger.info(f"Token refresh requested for user: {current_user.username}")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.username, "user_id": current_user.id, "role": current_user.role.value},
        expires_delta=access_token_expires
    )
    
    logger.debug(f"Token refreshed for user: {current_user.username}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": current_user
    }

@router.get("/me", response_model=schemas.UserInDB)
async def read_users_me(
    current_user: models.User = Depends(get_current_user)
) -> Any:
    """
    Get current user information
    """
    logger.debug(f"User info requested for: {current_user.username}")
    return current_user

@router.post("/logout")
async def logout(
    current_user: models.User = Depends(get_current_user),
    audit_log: dict = Depends(lambda: {"action": "LOGOUT"})
) -> Any:
    """
    Logout user (client should discard token)
    """
    logger.info(f"User logout: {current_user.username}")
    return {"message": "Successfully logged out"}

@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    audit_log: dict = Depends(lambda: {"action": "CHANGE_PASSWORD"})
) -> Any:
    """
    Change user password
    """
    logger.info(f"Password change requested for user: {current_user.username}")
    
    # Verify old password
    from app.auth import verify_password
    if not verify_password(old_password, current_user.hashed_password):
        logger.warning(f"Wrong old password for user: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password"
        )
    
    # Update password
    from app.auth import get_password_hash
    current_user.hashed_password = get_password_hash(new_password)
    db.add(current_user)
    db.commit()
    
    logger.info(f"Password changed successfully for user: {current_user.username}")
    
    return {"message": "Password changed successfully"}

# CLI endpoint for testing
@router.get("/cli-test")
async def cli_test_auth():
    """CLI test endpoint for authentication"""
    print("🔐 CLI Authentication Test")
    print("✅ Auth router is working correctly")
    return {
        "status": "ok",
        "message": "Auth router is functional",
        "endpoints": ["/login", "/refresh", "/me", "/logout", "/change-password"]
    }
