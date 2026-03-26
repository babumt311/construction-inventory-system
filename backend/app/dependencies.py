"""
Dependencies for FastAPI routes
"""
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Query, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import logging
from datetime import datetime
import jwt
from jwt import PyJWTError

from app.database import get_db
from app import models, schemas

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Try to get SECRET_KEY from config, with fallback
try:
    from app.config import settings
    SECRET_KEY = settings.SECRET_KEY
    ALGORITHM = settings.ALGORITHM
except ImportError:
    # Fallback values - should be overridden in production
    SECRET_KEY = "your-secret-key-change-this-in-production"
    ALGORITHM = "HS256"


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
# TOKEN VERIFICATION FUNCTION
# ============================================
def verify_token(token: str) -> dict:
    """
    Verify JWT token and return payload
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except PyJWTError as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================
# AUTHENTICATION DEPENDENCIES
# ============================================
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Get current authenticated user from token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
    
    try:
        payload = verify_token(token)
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


async def get_admin_user_dependency(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    Ensure current user has ADMIN role
    """
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def get_owner_or_admin_user_dependency(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    Ensure current user has OWNER or ADMIN role
    """
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or Admin access required"
        )
    return current_user


async def verify_user_ownership_or_admin(
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Verify that the current user owns the requested resource or is admin
    Used for IDOR prevention
    """
    # Admin can access any user
    if current_user.role == schemas.UserRole.ADMIN:
        return current_user
    
    # Owners can access users they own (if relationship exists)
    if current_user.role == schemas.UserRole.OWNER:
        # Check if this owner has access to the requested user
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user and getattr(user, 'owner_id', None) == current_user.id:
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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Log user actions for audit trail
    Returns a dict with audit info that can be extended by endpoints
    """
    audit_data = {
        "user_id": current_user.id,
        "username": current_user.username,
        "timestamp": datetime.utcnow(),
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host if request.client else None,
    }
    
    # You can optionally store this in a database table
    logger.info(f"Audit: {audit_data}")
    
    # Return the audit data so endpoints can add more details
    return audit_data


# ============================================
# SIMPLE TOKEN CREATE FUNCTION (for auth.py)
# ============================================
def create_access_token(data: dict) -> str:
    """
    Create JWT access token
    """
    from datetime import timedelta
    
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
