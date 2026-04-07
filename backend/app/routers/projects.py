"""
Project and Site management router
"""

from typing import Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel
import logging

from app import schemas, crud, models
from app.database import get_db
from app.models import Site, Task, ProjectTeamMember
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
# PROJECTS API
# ==========================================
@router.post("/", response_model=schemas.ProjectInDB)
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

@router.get("/", response_model=List[schemas.ProjectInDB])
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
# FORGIVING SCHEMAS (Prevent 422 Crashes)
# ==========================================
class ForgivingTeamMemberCreate(BaseModel):
    name: Optional[str] = None
    full_name: Optional[str] = None
    email: str
    role: Optional[str] = None
    project_role: Optional[str] = None

class ForgivingTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "Medium"
    estimated_hours: Optional[float] = 0.0
    due_date: Optional[Any] = None
    status: Optional[str] = "TO DO"

class ForgivingTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    estimated_hours: Optional[float] = None
    due_date: Optional[Any] = None
    status: Optional[str] = None

def parse_forgiving_date(date_val: Any) -> Optional[datetime]:
    if not date_val: return None
    try:
        if isinstance(date_val, str):
            if "-" in date_val and len(date_val.split("-")[0]) == 2:
                return datetime.strptime(date_val, "%d-%m-%Y")
            return datetime.fromisoformat(date_val.replace('Z', ''))
        return date_val
    except Exception:
        return None


# ==========================================
# TEAM API (POSTGRES PERSISTENT)
# ==========================================
@router.get("/{project_id}/team")
def get_project_team(project_id: int, db: Session = Depends(get_db)):
    return db.query(ProjectTeamMember).filter(ProjectTeamMember.project_id == project_id).all()

@router.post("/{project_id}/team")
def add_team_member(project_id: int, member: ForgivingTeamMemberCreate, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    actual_name = member.name or member.full_name or "Unknown User"
    actual_role = member.role or member.project_role or "Member"
        
    db_member = ProjectTeamMember(
        project_id=project_id,
        name=actual_name,
        email=member.email,
        role=actual_role
    )
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member

@router.delete("/{project_id}/team/{member_id}")
def delete_team_member(project_id: int, member_id: int, db: Session = Depends(get_db)):
    member = db.query(ProjectTeamMember).filter(
        ProjectTeamMember.id == member_id, 
        ProjectTeamMember.project_id == project_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    db.delete(member)
    db.commit()
    return {"message": "Deleted"}

# ==========================================
# TASKS API (POSTGRES PERSISTENT)
# ==========================================
@router.get("/{project_id}/tasks")
def get_project_tasks(project_id: int, db: Session = Depends(get_db)):
    return db.query(Task).filter(Task.project_id == project_id).all()

@router.post("/{project_id}/tasks")
def create_project_task(project_id: int, task: ForgivingTaskCreate, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    parsed_date = parse_forgiving_date(task.due_date)

    db_task = Task(
        project_id=project_id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        estimated_hours=task.estimated_hours,
        due_date=parsed_date,
        status=task.status
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@router.put("/{project_id}/tasks/{task_id}")
def update_project_task(project_id: int, task_id: int, task_update: ForgivingTaskUpdate, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(
        Task.id == task_id, 
        Task.project_id == project_id
    ).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    update_data = task_update.dict(exclude_unset=True)
    if "due_date" in update_data:
        update_data["due_date"] = parse_forgiving_date(update_data["due_date"])
        
    for key, value in update_data.items():
        setattr(db_task, key, value)
        
    db.commit()
    db.refresh(db_task)
    return db_task

@router.delete("/{project_id}/tasks/{task_id}")
def delete_project_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(
        Task.id == task_id, 
        Task.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"message": "Deleted"}
