from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app import models

router = APIRouter(prefix="/projects/{project_id}/team", tags=["Team"])

# Ultra-forgiving schema to catch whatever the frontend sends
class TeamMemberCreate(BaseModel):
    name: Optional[str] = None
    full_name: Optional[str] = None
    email: str
    role: Optional[str] = None
    project_role: Optional[str] = None

@router.get("/")
def get_team_members(project_id: int, db: Session = Depends(get_db)):
    return db.query(models.ProjectTeamMember).filter(models.ProjectTeamMember.project_id == project_id).all()

@router.post("/")
def add_team_member(project_id: int, member: TeamMemberCreate, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Safely map whatever field the frontend decided to use
    actual_name = member.name or member.full_name or "Unknown User"
    actual_role = member.role or member.project_role or "Member"
        
    db_member = models.ProjectTeamMember(
        project_id=project_id,
        name=actual_name,
        email=member.email,
        role=actual_role
    )
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member

@router.delete("/{member_id}")
def remove_team_member(project_id: int, member_id: int, db: Session = Depends(get_db)):
    member = db.query(models.ProjectTeamMember).filter(models.ProjectTeamMember.id == member_id, models.ProjectTeamMember.project_id == project_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    db.delete(member)
    db.commit()
    return {"message": "Team member removed"}
