"""
Site management router
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
from app.dependencies import (
    get_owner_or_admin_user_dependency,
    get_current_user_dependency,
    PaginationParams,
    log_audit_action,
    validate_project_access
)

router = APIRouter(prefix="/sites", tags=["sites"])
logger = logging.getLogger(__name__)

@router.post("/", response_model=schemas.SiteInDB)
async def create_site(
    site_in: schemas.SiteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Create new site (Admin/Owner only)
    """
    logger.info(f"Creating new site: {site_in.name} by {current_user.username}")
    
    # Check if user has access to the project
    from app.auth import check_project_access
    check_project_access(current_user, site_in.project_id, db)
    
    # Check if site code already exists in the project
    if site_in.code:
        existing_site = db.query(models.Site).filter(
            models.Site.project_id == site_in.project_id,
            models.Site.code == site_in.code
        ).first()
        if existing_site:
            logger.warning(f"Site code already exists in project: {site_in.code}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Site code already exists in this project"
            )
    
    # Create site
    site = crud.crud_site.create(db, obj_in=site_in)
    
    logger.info(f"Site created successfully: {site.name} (ID: {site.id})")
    return site

@router.get("/", response_model=List[schemas.SiteInDB])
async def read_sites(
    project_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Retrieve sites with optional filtering
    """
    logger.debug(f"Reading sites by user: {current_user.username}")
    
    query = db.query(models.Site)
    
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
        query = query.filter(models.Site.project_id == project_id)
    
    if status_filter:
        query = query.filter(models.Site.status == status_filter)
    
    # Apply sorting
    if pagination.sort_by:
        if hasattr(models.Site, pagination.sort_by):
            if pagination.sort_order == "desc":
                query = query.order_by(getattr(models.Site, pagination.sort_by).desc())
            else:
                query = query.order_by(getattr(models.Site, pagination.sort_by).asc())
    else:
        query = query.order_by(models.Site.created_at.desc())
    
    # Apply pagination
    sites = query.offset(pagination.skip).limit(pagination.size).all()
    
    logger.debug(f"Returning {len(sites)} sites")
    return sites

@router.get("/{site_id}", response_model=schemas.SiteInDB)
async def read_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Get site by ID
    """
    logger.debug(f"Reading site ID: {site_id}")
    
    site = crud.crud_site.get(db, id=site_id)
    
    if not site:
        logger.warning(f"Site not found: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # Check access to project
    from app.auth import check_project_access
    check_project_access(current_user, site.project_id, db)
    
    return site

@router.put("/{site_id}", response_model=schemas.SiteInDB)
async def update_site(
    site_id: int,
    site_in: schemas.SiteUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Update site (Admin/Owner only)
    """
    logger.info(f"Updating site ID: {site_id} by {current_user.username}")
    
    site = crud.crud_site.get(db, id=site_id)
    
    if not site:
        logger.warning(f"Site not found for update: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # Check access to project
    from app.auth import check_project_access
    check_project_access(current_user, site.project_id, db)
    
    # Check if new code already exists in the project
    if site_in.code and site_in.code != site.code:
        existing_site = db.query(models.Site).filter(
            models.Site.project_id == site.project_id,
            models.Site.code == site_in.code
        ).first()
        if existing_site:
            logger.warning(f"Site code already exists in project: {site_in.code}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Site code already exists in this project"
            )
    
    updated_site = crud.crud_site.update(db, db_obj=site, obj_in=site_in)
    
    logger.info(f"Site updated successfully: {updated_site.name}")
    return updated_site

@router.delete("/{site_id}")
async def delete_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Delete site (Admin/Owner only)
    """
    logger.info(f"Deleting site ID: {site_id} by {current_user.username}")
    
    site = crud.crud_site.get(db, id=site_id)
    
    if not site:
        logger.warning(f"Site not found for deletion: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # Check access to project
    from app.auth import check_project_access
    check_project_access(current_user, site.project_id, db)
    
    # Check if site has stock entries
    stock_entries = db.query(models.StockEntry).filter(
        models.StockEntry.site_id == site_id
    ).count()
    
    if stock_entries > 0:
        logger.warning(f"Cannot delete site with stock entries: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete site that has stock entries. Remove stock entries first."
        )
    
    deleted_site = crud.crud_site.delete(db, id=site_id)
    
    logger.info(f"Site deleted successfully: ID {site_id}")
    return {"message": "Site deleted successfully"}

@router.get("/project/{project_id}/active", response_model=List[schemas.SiteInDB])
async def read_active_sites(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    project_access: int = Depends(validate_project_access)
) -> Any:
    """
    Get active sites for a project
    """
    logger.debug(f"Getting active sites for project: {project_id}")
    
    sites = crud.crud_site.get_active_sites(db, project_id)
    
    logger.debug(f"Returning {len(sites)} active sites")
    return sites

@router.post("/{site_id}/close")
async def close_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Close a site (mark as completed)
    """
    logger.info(f"Closing site ID: {site_id} by {current_user.username}")
    
    site = crud.crud_site.get(db, id=site_id)
    
    if not site:
        logger.warning(f"Site not found: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # Check access to project
    from app.auth import check_project_access
    check_project_access(current_user, site.project_id, db)
    
    site.status = "completed"
    db.add(site)
    db.commit()
    db.refresh(site)
    
    logger.info(f"Site closed: {site.name}")
    return {"message": "Site closed successfully"}

@router.post("/{site_id}/reopen")
async def reopen_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Reopen a closed site
    """
    logger.info(f"Reopening site ID: {site_id} by {current_user.username}")
    
    site = crud.crud_site.get(db, id=site_id)
    
    if not site:
        logger.warning(f"Site not found: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # Check access to project
    from app.auth import check_project_access
    check_project_access(current_user, site.project_id, db)
    
    site.status = "active"
    db.add(site)
    db.commit()
    db.refresh(site)
    
    logger.info(f"Site reopened: {site.name}")
    return {"message": "Site reopened successfully"}

@router.get("/{site_id}/stock-summary")
async def get_site_stock_summary(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Get stock summary for a site
    """
    logger.debug(f"Getting stock summary for site: {site_id}")
    
    site = crud.crud_site.get(db, id=site_id)
    
    if not site:
        logger.warning(f"Site not found: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # Check access to project
    from app.auth import check_project_access
    check_project_access(current_user, site.project_id, db)
    
    # Get stock summary using the StockCalculator
    from app.utils.stock_calculator import StockCalculator
    calculator = StockCalculator()
    summary = calculator.get_site_stock_summary(db, site_id)
    
    logger.debug(f"Returning stock summary for site {site_id}")
    return summary

# CLI endpoint
@router.get("/cli/list/{project_id}")
async def cli_list_sites(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
):
    """CLI endpoint to list sites for a project"""
    print(f"🏢 CLI Site List for Project {project_id}")
    
    # Check access to project
    from app.auth import check_project_access
    check_project_access(current_user, project_id, db)
    
    sites = crud.crud_site.get_by_project(db, project_id)
    
    print(f"📋 Sites: {len(sites)}")
    for site in sites:
        status_icon = "✅" if site.status == "active" else "🔒" if site.status == "completed" else "⚠️"
        print(f"  {status_icon} {site.code or 'N/A'}: {site.name} - {site.location or 'No location'}")
    
    return {
        "project_id": project_id,
        "sites_count": len(sites)
    }
