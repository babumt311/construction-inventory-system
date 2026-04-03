"""
Project and Site management router
"""

# Add to any router file if these imports are missing
from app.auth import check_project_access
from app.auth import get_admin_user_dependency  # Add this function if missing
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging
from app import schemas, crud, models
from app.database import get_db
from app.models import Site
from app.schemas import SiteCreate, SiteInDB
from app.dependencies import (
    get_owner_or_admin_user_dependency,
    get_current_user_dependency,
    PaginationParams,
    log_audit_action,
    validate_project_access
)

router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger(__name__)

@router.post("/", response_model=schemas.ProjectInDB)
async def create_project(
    project_in: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Create new project (Admin/Owner only)
    """
    logger.info(f"Creating new project: {project_in.name} by {current_user.username}")
    
    # Check if project code already exists
    existing_project = crud.crud_project.get_by_code(db, code=project_in.code)
    if existing_project:
        logger.warning(f"Project code already exists: {project_in.code}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project code already exists"
        )
    
    # Create project
    project = crud.crud_project.create(db, obj_in=project_in)
    
    logger.info(f"Project created successfully: {project.name} (ID: {project.id})")
    return project

@router.get("/", response_model=List[schemas.ProjectInDB])
async def read_projects(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Retrieve projects accessible to current user
    """
    logger.debug(f"Reading projects by user: {current_user.username}")
    
    # Admin can see all projects
    if current_user.role == schemas.UserRole.ADMIN:
        query = db.query(models.Project)
    else:
        # Owners and Users can only see projects they have access to
        query = db.query(models.Project).join(
            models.user_project_access
        ).filter(
            models.user_project_access.c.user_id == current_user.id
        )
    
    # Apply filters
    if status_filter:
        query = query.filter(models.Project.status == status_filter)
    
    # Apply sorting
    if pagination.sort_by:
        if hasattr(models.Project, pagination.sort_by):
            if pagination.sort_order == "desc":
                query = query.order_by(getattr(models.Project, pagination.sort_by).desc())
            else:
                query = query.order_by(getattr(models.Project, pagination.sort_by).asc())
    else:
        query = query.order_by(models.Project.created_at.desc())
    
    # Apply pagination
    projects = query.offset(pagination.skip).limit(pagination.size).all()
    
    logger.debug(f"Returning {len(projects)} projects")
    return projects

@router.get("/{project_id}", response_model=schemas.ProjectInDB)
async def read_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    project_access: int = Depends(validate_project_access)
) -> Any:
    """
    Get project by ID
    """
    logger.debug(f"Reading project ID: {project_id}")
    
    project = crud.crud_project.get(db, id=project_id)
    
    if not project:
        logger.warning(f"Project not found: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project

@router.put("/{project_id}", response_model=schemas.ProjectInDB)
async def update_project(
    project_id: int,
    project_in: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action),
    project_access: int = Depends(validate_project_access)
) -> Any:
    """
    Update project (Admin/Owner only)
    """
    logger.info(f"Updating project ID: {project_id} by {current_user.username}")
    
    project = crud.crud_project.get(db, id=project_id)
    
    if not project:
        logger.warning(f"Project not found for update: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check if new code already exists
    if project_in.code and project_in.code != project.code:
        existing_project = crud.crud_project.get_by_code(db, code=project_in.code)
        if existing_project:
            logger.warning(f"Project code already exists: {project_in.code}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project code already exists"
            )
    
    updated_project = crud.crud_project.update(db, db_obj=project, obj_in=project_in)
    
    logger.info(f"Project updated successfully: {updated_project.name}")
    return updated_project

@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Delete project (Admin only)
    """
    logger.info(f"Deleting project ID: {project_id} by admin: {current_user.username}")
    
    project = crud.crud_project.delete(db, id=project_id)
    
    if not project:
        logger.warning(f"Project not found for deletion: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    logger.info(f"Project deleted successfully: ID {project_id}")
    return {"message": "Project deleted successfully"}

@router.get("/{project_id}/sites", response_model=List[schemas.SiteInDB])
async def read_project_sites(
    project_id: int,
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    project_access: int = Depends(validate_project_access)
) -> Any:
    """
    Get sites for a project
    """
    logger.debug(f"Getting sites for project: {project_id}")
    
    query = db.query(models.Site).filter(models.Site.project_id == project_id)
    
    if status_filter:
        query = query.filter(models.Site.status == status_filter)
    
    sites = query.order_by(models.Site.created_at).all()
    
    logger.debug(f"Returning {len(sites)} sites")
    return sites

@router.post("/{project_id}/users/{user_id}")
async def add_user_to_project(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Add user to project (Admin/Owner only)
    """
    logger.info(f"Adding user {user_id} to project {project_id} by {current_user.username}")
    
    success = crud.crud_project.add_user_access(db, project_id, user_id)
    
    if not success:
        logger.warning(f"Failed to add user {user_id} to project {project_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add user to project"
        )
    
    logger.info(f"User {user_id} added to project {project_id}")
    return {"message": "User added to project successfully"}

@router.delete("/{project_id}/users/{user_id}")
async def remove_user_from_project(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Remove user from project (Admin/Owner only)
    """
    logger.info(f"Removing user {user_id} from project {project_id} by {current_user.username}")
    
    success = crud.crud_project.remove_user_access(db, project_id, user_id)
    
    if not success:
        logger.warning(f"Failed to remove user {user_id} from project {project_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove user from project"
        )
    
    logger.info(f"User {user_id} removed from project {project_id}")
    return {"message": "User removed from project successfully"}

# ==========================================
# SITES DATABASE API
# ==========================================

@router.get("/{project_id}/sites", response_model=list[SiteInDB])
def get_project_sites(project_id: int, db: Session = Depends(get_db)):
    """Fetch all sites saved in PostgreSQL for a specific project."""
    return db.query(Site).filter(Site.project_id == project_id).all()

@router.post("/{project_id}/sites", response_model=SiteInDB)
def create_project_site(project_id: int, site: SiteCreate, db: Session = Depends(get_db)):
    """Save a brand new site to PostgreSQL."""
    # Force the project_id to match the URL so it saves to the right place
    site_data = site.dict()
    site_data['project_id'] = project_id 
    
    db_site = Site(**site_data)
    db.add(db_site)
    db.commit()
    db.refresh(db_site)
    return db_site

@router.delete("/sites/{site_id}")
def delete_site(site_id: int, db: Session = Depends(get_db)):
    """Permanently delete a site from PostgreSQL."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if site:
        db.delete(site)
        db.commit()
    return {"message": "Site permanently deleted"}
