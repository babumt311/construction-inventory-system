"""
Purchase Order (PO) management router
"""

# Add to any router file if these imports are missing
from app.dependencies import get_owner_or_admin_user_dependency
from app.auth import check_project_access
from app.auth import get_admin_user_dependency  # Add this function if missing
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging
from datetime import datetime
from app import schemas, crud, models
from app.database import get_db
from app.dependencies import (
    get_current_user_dependency,
    PaginationParams,
    log_audit_action,
    validate_project_access
)

router = APIRouter(prefix="/po", tags=["purchase-orders"])
logger = logging.getLogger(__name__)

@router.post("/entries", response_model=schemas.POEntryInDB)
async def create_po_entry(
    po_in: schemas.POEntryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Create new purchase order entry
    """
    logger.info(f"Creating PO entry by user: {current_user.username}")
    
    # Check if user has access to the project
    from app.auth import check_project_access
    check_project_access(current_user, po_in.project_id, db)
    
    # Check if material exists
    material = crud.crud_material.get(db, id=po_in.material_id)
    if not material:
        logger.warning(f"Material not found: {po_in.material_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    # Create PO entry
    po_data = po_in.dict()
    po_data["created_by"] = current_user.id
    
    # Set PO date if not provided
    if not po_data.get("po_date"):
        po_data["po_date"] = datetime.now()
    
    po_entry = models.POEntry(**po_data)
    db.add(po_entry)
    db.commit()
    db.refresh(po_entry)
    
    logger.info(f"PO entry created: ID {po_entry.id}, invoice {po_entry.invoice_no}")
    return po_entry

@router.get("/entries", response_model=List[schemas.POEntryInDB])
async def read_po_entries(
    project_id: Optional[int] = Query(None),
    supplier_name: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Retrieve PO entries with filtering
    """
    logger.debug(f"Reading PO entries by user: {current_user.username}")
    
    query = db.query(models.POEntry)
    
    # Apply filters
    if project_id:
        # Check access to project
        from app.auth import check_project_access
        try:
            check_project_access(current_user, project_id, db)
        except HTTPException:
            # User doesn't have access to this project
            logger.warning(f"User {current_user.id} doesn't have access to project {project_id}")
            return []
        query = query.filter(models.POEntry.project_id == project_id)
    
    if supplier_name:
        query = query.filter(models.POEntry.supplier_name.ilike(f"%{supplier_name}%"))
    
    if start_date:
        query = query.filter(models.POEntry.po_date >= start_date)
    
    if end_date:
        query = query.filter(models.POEntry.po_date <= end_date)
    
    # Apply sorting
    if pagination.sort_by:
        if hasattr(models.POEntry, pagination.sort_by):
            if pagination.sort_order == "desc":
                query = query.order_by(getattr(models.POEntry, pagination.sort_by).desc())
            else:
                query = query.order_by(getattr(models.POEntry, pagination.sort_by).asc())
    else:
        query = query.order_by(models.POEntry.po_date.desc())
    
    # Apply pagination
    entries = query.offset(pagination.skip).limit(pagination.size).all()
    
    logger.debug(f"Returning {len(entries)} PO entries")
    return entries

@router.get("/entries/{entry_id}", response_model=schemas.POEntryInDB)
async def read_po_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Get PO entry by ID
    """
    logger.debug(f"Reading PO entry ID: {entry_id}")
    
    entry = crud.crud_po_entry.get(db, id=entry_id)
    
    if not entry:
        logger.warning(f"PO entry not found: {entry_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PO entry not found"
        )
    
    # Check access to project
    from app.auth import check_project_access
    check_project_access(current_user, entry.project_id, db)
    
    return entry

@router.put("/entries/{entry_id}", response_model=schemas.POEntryInDB)
async def update_po_entry(
    entry_id: int,
    po_in: schemas.POEntryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Update PO entry
    """
    logger.info(f"Updating PO entry ID: {entry_id} by user: {current_user.username}")
    
    entry = crud.crud_po_entry.get(db, id=entry_id)
    
    if not entry:
        logger.warning(f"PO entry not found: {entry_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PO entry not found"
        )
    
    # Check access to project
    from app.auth import check_project_access
    check_project_access(current_user, entry.project_id, db)
    
    # Only allow updates by the creator or admin/owner
    if entry.created_by != current_user.id and current_user.role not in [
        schemas.UserRole.ADMIN, schemas.UserRole.OWNER
    ]:
        logger.warning(f"User {current_user.id} not authorized to update PO entry {entry_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this PO entry"
        )
    
    # Update entry
    update_data = po_in.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if hasattr(entry, field):
            setattr(entry, field, value)
    
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    logger.info(f"PO entry updated: ID {entry_id}")
    return entry

@router.delete("/entries/{entry_id}")
async def delete_po_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Delete PO entry (Owner/Admin only)
    """
    logger.info(f"Deleting PO entry ID: {entry_id} by {current_user.username}")
    
    entry = crud.crud_po_entry.delete(db, id=entry_id)
    
    if not entry:
        logger.warning(f"PO entry not found: {entry_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PO entry not found"
        )
    
    logger.info(f"PO entry deleted: ID {entry_id}")
    return {"message": "PO entry deleted successfully"}

@router.get("/stats/{project_id}")
async def get_po_stats(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    project_access: int = Depends(validate_project_access)
) -> Any:
    """
    Get PO statistics for a project
    """
    logger.debug(f"Getting PO stats for project: {project_id}")
    
    # Total PO count
    total_po = db.query(models.POEntry).filter(
        models.POEntry.project_id == project_id
    ).count()
    
    # Total cost
    total_cost = crud.crud_po_entry.get_total_cost_by_project(db, project_id)
    
    # Suppliers count
    suppliers_count = db.query(models.POEntry.supplier_name).filter(
        models.POEntry.project_id == project_id
    ).distinct().count()
    
    # Recent PO entries
    recent_entries = db.query(models.POEntry).filter(
        models.POEntry.project_id == project_id
    ).order_by(models.POEntry.po_date.desc()).limit(5).all()
    
    return {
        "total_po_entries": total_po,
        "total_cost": float(total_cost),
        "suppliers_count": suppliers_count,
        "recent_entries": [
            {
                "id": entry.id,
                "invoice_no": entry.invoice_no,
                "supplier": entry.supplier_name,
                "date": entry.po_date,
                "total_cost": float(entry.total_cost)
            }
            for entry in recent_entries
        ]
    }

@router.get("/suppliers")
async def get_suppliers(
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Get list of suppliers
    """
    logger.debug("Getting suppliers list")
    
    query = db.query(models.POEntry.supplier_name).distinct()
    
    if project_id:
        # Check access to project
        from app.auth import check_project_access
        try:
            check_project_access(current_user, project_id, db)
        except HTTPException:
            # User doesn't have access to this project
            return []
        query = query.filter(models.POEntry.project_id == project_id)
    
    suppliers = [row[0] for row in query.all()]
    
    logger.debug(f"Found {len(suppliers)} suppliers")
    return suppliers

@router.get("/supplier-invoices")
async def get_supplier_invoices(
    supplier_name: str,
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Get invoices for a specific supplier
    """
    logger.debug(f"Getting invoices for supplier: {supplier_name}")
    
    query = db.query(models.POEntry).filter(
        models.POEntry.supplier_name == supplier_name
    )
    
    if project_id:
        # Check access to project
        from app.auth import check_project_access
        try:
            check_project_access(current_user, project_id, db)
        except HTTPException:
            # User doesn't have access to this project
            return []
        query = query.filter(models.POEntry.project_id == project_id)
    
    invoices = query.order_by(models.POEntry.po_date.desc()).all()
    
    return invoices
