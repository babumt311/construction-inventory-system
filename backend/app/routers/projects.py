"""
Project and Site management router
"""

import json
import os
import uuid
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, selectinload
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

# ==========================================
# PERSISTENT DOCKER VOLUME FOR TASKS & TEAMS
# (Survives docker compose down/up!)
# ==========================================
DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)
EC2_DATA_FILE = os.path.join(DATA_DIR, "ec2_persistent_data.json")

def _load_data():
    if not os.path.exists(EC2_DATA_FILE):
        return {"tasks": [], "team": []}
    with open(EC2_DATA_FILE, "r") as f:
        return json.load(f)

def _save_data(data):
    with open(EC2_DATA_FILE, "w") as f:
        json.dump(data, f)

# ==========================================
# PROJECTS API
# ==========================================
@router.post("", response_model=schemas.ProjectInDB)
async def create_project(
    project_in: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    logger.info(f"Creating new project: {project_in.name} by {current_user.username}")
    existing_project = crud.crud_project.get_by_code(db, code=project_in.code)
    if existing_project:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project code already exists")
    project = crud.crud_project.create(db, obj_in=project_in)
    return project

@router.get("", response_model=List[schemas.ProjectInDB])
async def read_projects(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    if current_user.role == schemas.UserRole.ADMIN:
        query = db.query(models.Project).options(selectinload(models.Project.sites))
    else:
        query = db.query(models.Project).join(models.user_project_access).filter(
            models.user_project_access.c.user_id == current_user.id
        ).options(selectinload(models.Project.sites))
    
    if status_filter:
        query = query.filter(models.Project.status == status_filter)
    
    if pagination.sort_by:
        if hasattr(models.Project, pagination.sort_by):
            if pagination.sort_order == "desc":
                query = query.order_by(getattr(models.Project, pagination.sort_by).desc())
            else:
                query = query.order_by(getattr(models.Project, pagination.sort_by).asc())
    else:
        query = query.order_by(models.Project.created_at.desc())
    
    projects = query.offset(pagination.skip).limit(pagination.size).all()
    return projects

@router.get("/{project_id}", response_model=schemas.ProjectInDB)
async def read_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    project_access: int = Depends(validate_project_access)
) -> Any:
    project = crud.crud_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
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
    project = crud.crud_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project_in.code and project_in.code != project.code:
        existing_project = crud.crud_project.get_by_code(db, code=project_in.code)
        if existing_project:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project code already exists")
    updated_project = crud.crud_project.update(db, db_obj=project, obj_in=project_in)
    return updated_project

@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    project = crud.crud_project.delete(db, id=project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return {"message": "Project deleted successfully"}

# ==========================================
# SITES API
# ==========================================
@router.get("/{project_id}/sites", response_model=list[SiteInDB])
def get_project_sites(project_id: int, db: Session = Depends(get_db)):
    """Fetch all sites saved in PostgreSQL for a specific project."""
    return db.query(Site).filter(Site.project_id == project_id).all()

@router.post("/{project_id}/sites", response_model=SiteInDB)
def create_project_site(project_id: int, site: SiteCreate, db: Session = Depends(get_db)):
    """Save a brand new site to PostgreSQL."""
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

# ==========================================
# TEAM API (JSON PERSISTENT)
# ==========================================
@router.get("/{project_id}/team")
def get_project_team(project_id: str):
    data = _load_data()
    return [t for t in data.get("team", []) if str(t.get("project_id")) == str(project_id)]

@router.post("/{project_id}/team")
def add_team_member(project_id: str, member: dict):
    data = _load_data()
    member["id"] = str(uuid.uuid4())
    member["project_id"] = str(project_id)
    data["team"].append(member)
    _save_data(data)
    return member

@router.delete("/{project_id}/team/{member_id}")
def delete_team_member(project_id: str, member_id: str):
    data = _load_data()
    data["team"] = [t for t in data.get("team", []) if str(t.get("id")) != str(member_id)]
    _save_data(data)
    return {"message": "Deleted"}

# ==========================================
# TASKS API (JSON PERSISTENT)
# ==========================================
@router.get("/{project_id}/tasks")
def get_project_tasks(project_id: str):
    data = _load_data()
    return [t for t in data.get("tasks", []) if str(t.get("project_id")) == str(project_id)]

@router.post("/{project_id}/tasks")
def create_project_task(project_id: str, task: dict):
    data = _load_data()
    task["id"] = str(uuid.uuid4())
    task["project_id"] = str(project_id)
    data["tasks"].append(task)
    _save_data(data)
    return task

@router.put("/{project_id}/tasks/{task_id}")
def update_project_task(project_id: str, task_id: str, task_update: dict):
    data = _load_data()
    for t in data["tasks"]:
        if str(t.get("id")) == str(task_id):
            t.update(task_update)
            break
    _save_data(data)
    return {"message": "Updated"}

@router.delete("/{project_id}/tasks/{task_id}")
def delete_project_task(project_id: str, task_id: str):
    data = _load_data()
    data["tasks"] = [t for t in data.get("tasks", []) if str(t.get("id")) != str(task_id)]
    _save_data(data)
    return {"message": "Deleted"}
