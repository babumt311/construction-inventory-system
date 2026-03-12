"""
Authentication and authorization utilities
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app import models, schemas
from app.database import get_db
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against hashed password"""
    logger.debug("Verifying password")
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    logger.debug("Hashing password")
    return pwd_context.hash(password)

def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    """Authenticate user with username and password"""
    logger.info(f"Attempting authentication for user: {username}")
    
    user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == username)
    ).first()
    
    if not user:
        logger.warning(f"User not found: {username}")
        return None
    
    if not verify_password(password, user.hashed_password):
        logger.warning(f"Invalid password for user: {username}")
        return None
    
    if not user.is_active:
        logger.warning(f"Inactive user attempt: {username}")
        return None
    
    logger.info(f"User authenticated successfully: {username}")
    return user

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    logger.debug("Creating access token")
    
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    logger.debug(f"Access token created, expires at: {expire}")
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """Get current user from JWT token"""
    logger.debug("Getting current user from token")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if username is None or user_id is None:
            logger.error("Invalid token payload")
            raise credentials_exception
            
        token_data = schemas.TokenData(username=username, user_id=user_id)
        
    except JWTError as e:
        logger.error(f"JWT error: {str(e)}")
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.id == token_data.user_id).first()
    
    if user is None:
        logger.error(f"User not found for token: {token_data.user_id}")
        raise credentials_exception
    
    if not user.is_active:
        logger.warning(f"Inactive user attempting access: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    logger.debug(f"Current user retrieved: {user.username}")
    return user

async def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Get current active user"""
    if not current_user.is_active:
        logger.warning(f"Inactive user: {current_user.username}")
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Role-based access control functions
def require_role(required_role: schemas.UserRole):
    """Decorator to require specific role for endpoint access"""
    def role_checker(current_user: models.User = Depends(get_current_active_user)):
        logger.debug(f"Checking role for user {current_user.username}: {current_user.role}, required: {required_role}")
        
        if current_user.role != required_role:
            logger.warning(f"Role mismatch for user {current_user.username}: {current_user.role} != {required_role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role.value} role"
            )
        return current_user
    return role_checker

def require_admin(current_user: models.User = Depends(get_current_active_user)):
    """Require admin role"""
    logger.debug(f"Checking admin role for user: {current_user.username}")
    
    if current_user.role != schemas.UserRole.ADMIN:
        logger.warning(f"Non-admin user attempting admin action: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires admin role"
        )
    return current_user

def require_owner_or_admin(current_user: models.User = Depends(get_current_active_user)):
    """Require owner or admin role"""
    logger.debug(f"Checking owner/admin role for user: {current_user.username}")
    
    if current_user.role not in [schemas.UserRole.OWNER, schemas.UserRole.ADMIN]:
        logger.warning(f"Non-owner/admin user attempting action: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires owner or admin role"
        )
    return current_user

def has_project_access(user: models.User, project_id: int) -> bool:
    """Check if user has access to a specific project"""
    logger.debug(f"Checking project access for user {user.id} to project {project_id}")
    
    # Admin has access to all projects
    if user.role == schemas.UserRole.ADMIN:
        return True
    
    # Owner can access projects they're assigned to
    if user.role == schemas.UserRole.OWNER:
        return any(project.id == project_id for project in user.projects)
    
    # Regular users can only access assigned projects
    return any(project.id == project_id for project in user.projects)

def check_project_access(
    user: models.User,
    project_id: int,
    db: Session
):
    """Check and raise exception if user doesn't have project access"""
    logger.debug(f"Validating project access for user {user.id} to project {project_id}")
    
    if not has_project_access(user, project_id):
        logger.warning(f"User {user.id} does not have access to project {project_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this project"
        )

def create_admin_user(db: Session):
    """Create default admin user if not exists"""
    logger.info("Checking for admin user creation")
    
    admin = db.query(models.User).filter(models.User.username == "admin").first()
    
    if not admin:
        logger.info("Creating default admin user")
        admin_user = models.User(
            username="admin",
            email="admin@construction.com",
            full_name="System Administrator",
            hashed_password=get_password_hash("Admin@123"),
            role=schemas.UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        logger.info("Default admin user created successfully")
    else:
        logger.info("Admin user already exists")


def get_admin_user_dependency(
    current_user: models.User = Depends(get_current_active_user)
) -> models.User:
    """Dependency to require admin user"""
    if current_user.role != schemas.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires admin role"
        )
    return current_user


# CLI functions for authentication
def cli_authenticate_user(db: Session, username: str, password: str) -> Optional[Dict[str, Any]]:
    """CLI version of user authentication"""
    print(f"🔐 Authenticating user: {username}")
    
    user = authenticate_user(db, username, password)
    
    if user:
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id, "role": user.role.value}
        )
        
        print(f"✅ Authentication successful for {user.username}")
        print(f"   Role: {user.role.value}")
        print(f"   Token: {access_token[:50]}...")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user
        }
    else:
        print(f"❌ Authentication failed for {username}")
        return None
