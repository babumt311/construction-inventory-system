"""
Report generation router
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging
from datetime import datetime, date
from app import schemas, crud, models
from app.database import get_db
from app.dependencies import (
    get_current_active_user_dependency,
    get_owner_or_admin_user_dependency,
    ReportFilterParams,
    log_audit_action,
    validate_project_access
)
from app.utils.report_generator import ReportGenerator

router = APIRouter(prefix="/reports", tags=["reports"])
logger = logging.getLogger(__name__)


@router.get("/material-wise", response_model=List[schemas.MaterialWiseReport])
async def get_material_wise_report(
    filters: ReportFilterParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user_dependency)
) -> Any:
    """
    Generate material-wise report
    """
    logger.info(f"Generating material-wise report for user: {current_user.username}")
    
    # Check project access if project_id is provided
    if filters.project_id:
        validate_project_access(filters.project_id, current_user, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_material_wise_report(
        db,
        filters.project_id,
        filters.start_date,
        filters.end_date
    )
    
    logger.debug(f"Generated material-wise report with {len(report_data)} rows")
    return report_data


@router.get("/supplier-wise", response_model=List[schemas.SupplierWiseReport])
async def get_supplier_wise_report(
    filters: ReportFilterParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user_dependency)
) -> Any:
    """
    Generate supplier-wise report
    """
    logger.info(f"Generating supplier-wise report for user: {current_user.username}")
    
    # Check project access if project_id is provided
    if filters.project_id:
        validate_project_access(filters.project_id, current_user, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_supplier_wise_report(
        db,
        filters.project_id,
        filters.supplier_name,
        filters.start_date,
        filters.end_date
    )
    
    logger.debug(f"Generated supplier-wise report with {len(report_data)} rows")
    return report_data


@router.get("/supplier-summary")
async def get_supplier_summary_report(
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user_dependency)
) -> Any:
    """
    Generate supplier summary report
    """
    logger.info(f"Generating supplier summary report for user: {current_user.username}")
    
    # Check project access if project_id is provided
    if project_id:
        validate_project_access(project_id, current_user, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_supplier_summary_report(db, project_id)
    
    logger.debug(f"Generated supplier summary report with {len(report_data)} rows")
    return report_data


@router.get("/period")
async def get_period_report(
    site_id: int = Query(..., description="Site ID"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    material_id: Optional[int] = Query(None, description="Material ID filter"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user_dependency)
) -> Any:
    """
    Generate period report (weekly/monthly/annual)
    """
    logger.info(f"Generating period report for user: {current_user.username}")
    
    # Get site and check project access
    site = crud.crud_site.get(db, id=site_id)
    if not site:
        logger.warning(f"Site not found: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    validate_project_access(site.project_id, current_user, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_period_report(
        db, site_id, start_date, end_date, material_id
    )
    
    logger.debug(f"Generated period report with {len(report_data)} rows")
    return report_data


@router.get("/custom")
async def get_custom_report(
    filters: ReportFilterParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user_dependency)
) -> Any:
    """
    Generate custom report based on filters
    """
    logger.info(f"Generating custom report for user: {current_user.username}")
    
    # Check project access if project_id is provided
    if filters.project_id:
        validate_project_access(filters.project_id, current_user, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_custom_report(db, filters)
    
    logger.debug(f"Generated custom report with {len(report_data)} rows")
    return report_data


@router.get("/stock-valuation")
async def get_stock_valuation_report(
    site_id: Optional[int] = Query(None, description="Site ID filter"),
    project_id: Optional[int] = Query(None, description="Project ID filter"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user_dependency)
) -> Any:
    """
    Generate stock valuation report
    """
    logger.info(f"Generating stock valuation report for user: {current_user.username}")
    
    # Check project access if project_id is provided
    if project_id:
        validate_project_access(project_id, current_user, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_stock_valuation_report(db, site_id, project_id)
    
    logger.debug(f"Generated stock valuation report with {len(report_data)} rows")
    return report_data


@router.get("/export/{report_type}")
async def export_report(
    report_type: str,  # Path parameter - NO Query() here!
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    project_id: Optional[int] = Query(None, description="Project ID"),
    site_id: Optional[int] = Query(None, description="Site ID"),
    material_id: Optional[int] = Query(None, description="Material ID"),
    supplier_name: Optional[str] = Query(None, description="Supplier name"),
    category_id: Optional[int] = Query(None, description="Category ID"),
    format: str = Query("excel", regex="^(excel|csv|pdf)$", description="Export format"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Export report to Excel, CSV, or PDF
    """
    logger.info(f"Exporting {report_type} report for user: {current_user.username}")
    
    # Validate report type
    valid_report_types = ["material-wise", "supplier-wise", "supplier-summary", "period", "stock-valuation"]
    if report_type not in valid_report_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type. Must be one of: {valid_report_types}"
        )
    
    # Check project access if project_id is provided
    if project_id:
        validate_project_access(project_id, current_user, db)
    
    # Generate report data
    generator = ReportGenerator()
    report_data = []
    
    try:
        if report_type == "material-wise":
            report_data = generator.generate_material_wise_report(
                db, project_id, start_date, end_date
            )
        elif report_type == "supplier-wise":
            report_data = generator.generate_supplier_wise_report(
                db, project_id, supplier_name, start_date, end_date
            )
        elif report_type == "supplier-summary":
            report_data = generator.generate_supplier_summary_report(db, project_id)
        elif report_type == "period":
            if not site_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Site ID is required for period reports"
                )
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Start date and end date are required for period reports"
                )
            report_data = generator.generate_period_report(
                db, site_id, start_date, end_date, material_id
            )
        elif report_type == "stock-valuation":
            report_data = generator.generate_stock_valuation_report(db, site_id, project_id)
        
        # Export based on format
        if format == "excel":
            return generator.export_to_excel(report_data, report_type)
        elif format == "csv":
            return generator.export_to_csv(report_data, report_type)
        elif format == "pdf":
            return generator.export_to_pdf(report_data, report_type)
        else:
            return report_data
            
    except Exception as e:
        logger.error(f"Error exporting report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating report: {str(e)}"
        )
