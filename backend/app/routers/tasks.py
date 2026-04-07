from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from app.database import get_db
from app import models

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["Tasks"])

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "Medium"
    estimated_hours: Optional[float] = 0.0
    due_date: Optional[Any] = None  # Accept ANYTHING to stop 422 crashes
    status: Optional[str] = "TO DO"

@router.get("/")
def get_tasks(project_id: int, db: Session = Depends(get_db)):
    return db.query(models.Task).filter(models.Task.project_id == project_id).all()

@router.post("/")
def create_task(project_id: int, task: TaskCreate, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Safely handle potential weird date strings from Angular
    parsed_date = None
    if task.due_date:
        try:
            if isinstance(task.due_date, str):
                # Try to parse frontend's DD-MM-YYYY or YYYY-MM-DD formats safely
                if "-" in task.due_date and len(task.due_date.split("-")[0]) == 2:
                    parsed_date = datetime.strptime(task.due_date, "%d-%m-%Y")
                else:
                    parsed_date = datetime.fromisoformat(task.due_date.replace('Z', ''))
            else:
                parsed_date = task.due_date
        except Exception:
            parsed_date = None # Fallback safely instead of crashing

    db_task = models.Task(
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

@router.delete("/{task_id}")
def delete_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id, models.Task.project_id == project_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}
