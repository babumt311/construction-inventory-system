"""
Authentication helper functions
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
import logging

from app import models, schemas
from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ============================================
# PASSWORD FUNCTIONS
# ============================================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


# ============================================
# USER AUTHENTICATION
# ============================================
def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    """Authenticate a user by username/email and password"""
    # Try to find user by username
    user = db.query(models.User).filter(
        models.User.username == username
    ).first()
    
    # If not found by username, try email
    if not user:
        user = db.query(models.User).filter(
            models.User.email == username
        ).first()
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    return user


# ============================================
# TOKEN FUNCTIONS
# ============================================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """Get current authenticated user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
    
    try:
        payload = verify_token(token)
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if username is None or user_id is None:
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


def get_admin_user_dependency(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Ensure current user has ADMIN role"""
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def get_owner_or_admin_dependency(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Ensure current user has OWNER or ADMIN role"""
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or Admin access required"
        )
    return current_user


def check_project_access(project_id: int, current_user: models.User, db: Session) -> bool:
    """Check if user has access to a project"""
    # Admin has access to all projects
    if current_user.role == schemas.UserRole.ADMIN:
        return True
    
    # Owner can access their projects
    if current_user.role == schemas.UserRole.OWNER:
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if project and project.owner_id == current_user.id:
            return True
    
    # Regular users can access projects they're assigned to
    # This assumes a many-to-many relationship between users and projects
    # Adjust based on your actual model
    if hasattr(current_user, 'projects'):
        for project in current_user.projects:
            if project.id == project_id:
                return True
    
    return False
