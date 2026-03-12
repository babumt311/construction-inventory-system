"""
Report generation router
"""

# Add to any router file if these imports are missing
from app.auth import check_project_access
from app.auth import get_admin_user_dependency  # Add this function if missing
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging
from datetime import datetime, date
from fastapi.responses import StreamingResponse
from app import schemas, crud, models
from app.database import get_db
from app.dependencies import (
    get_current_user_dependency,
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
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Generate material-wise report
    """
    logger.info(f"Generating material-wise report for user: {current_user.username}")
    
    # Convert filter params to ReportFilter schema
    report_filter = schemas.ReportFilter(
        start_date=filters.start_date,
        end_date=filters.end_date,
        project_id=filters.project_id,
        site_id=filters.site_id,
        material_id=filters.material_id,
        supplier_name=filters.supplier_name,
        category_id=filters.category_id
    )
    
    # Check project access if project_id is provided
    if report_filter.project_id:
        from app.auth import check_project_access
        check_project_access(current_user, report_filter.project_id, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_material_wise_report(
        db,
        report_filter.project_id,
        report_filter.start_date,
        report_filter.end_date
    )
    
    logger.debug(f"Generated material-wise report with {len(report_data)} rows")
    return report_data

@router.get("/supplier-wise", response_model=List[schemas.SupplierWiseReport])
async def get_supplier_wise_report(
    filters: ReportFilterParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Generate supplier-wise report
    """
    logger.info(f"Generating supplier-wise report for user: {current_user.username}")
    
    # Convert filter params to ReportFilter schema
    report_filter = schemas.ReportFilter(
        start_date=filters.start_date,
        end_date=filters.end_date,
        project_id=filters.project_id,
        site_id=filters.site_id,
        material_id=filters.material_id,
        supplier_name=filters.supplier_name,
        category_id=filters.category_id
    )
    
    # Check project access if project_id is provided
    if report_filter.project_id:
        from app.auth import check_project_access
        check_project_access(current_user, report_filter.project_id, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_supplier_wise_report(
        db,
        report_filter.project_id,
        report_filter.supplier_name,
        report_filter.start_date,
        report_filter.end_date
    )
    
    logger.debug(f"Generated supplier-wise report with {len(report_data)} rows")
    return report_data

@router.get("/supplier-summary")
async def get_supplier_summary_report(
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Generate supplier summary report
    """
    logger.info(f"Generating supplier summary report for user: {current_user.username}")
    
    # Check project access if project_id is provided
    if project_id:
        from app.auth import check_project_access
        check_project_access(current_user, project_id, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_supplier_summary_report(db, project_id)
    
    logger.debug(f"Generated supplier summary report with {len(report_data)} rows")
    return report_data

@router.get("/period")
async def get_period_report(
    site_id: int,
    start_date: date,
    end_date: date,
    material_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
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
    
    from app.auth import check_project_access
    check_project_access(current_user, site.project_id, db)
    
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
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Generate custom report based on filters
    """
    logger.info(f"Generating custom report for user: {current_user.username}")
    
    # Convert filter params to ReportFilter schema
    report_filter = schemas.ReportFilter(
        start_date=filters.start_date,
        end_date=filters.end_date,
        project_id=filters.project_id,
        site_id=filters.site_id,
        material_id=filters.material_id,
        supplier_name=filters.supplier_name,
        category_id=filters.category_id
    )
    
    # Check project access if project_id is provided
    if report_filter.project_id:
        from app.auth import check_project_access
        check_project_access(current_user, report_filter.project_id, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_custom_report(db, report_filter)
    
    logger.debug(f"Generated custom report with {len(report_data)} rows")
    return report_data

@router.get("/stock-valuation")
async def get_stock_valuation_report(
    site_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Generate stock valuation report
    """
    logger.info(f"Generating stock valuation report for user: {current_user.username}")
    
    # Check project access if project_id is provided
    if project_id:
        from app.auth import check_project_access
        check_project_access(current_user, project_id, db)
    
    # Generate report
    generator = ReportGenerator()
    report_data = generator.generate_stock_valuation_report(db, site_id, project_id)
    
    logger.debug(f"Generated stock valuation report with {len(report_data)} rows")
    return report_data

@router.get("/export/{report_type}")
async def export_report(
    report_type: str,
    filters: ReportFilterParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Export report to Excel
    """
    logger.info(f"Exporting {report_type} report for user: {current_user.username}")
    
    # Convert filter params to ReportFilter schema
    report_filter = schemas.ReportFilter(
        start_date=filters.start_date,
        end_date=filters.end_date,
        project_id=filters.project_id,
        site_id=filters.site_id,
        material_id=filters.material_id,
        supplier_name=filters.supplier_name,
        category_id=filters.category_id
    )
    
    # Check project access if project_id is provided
    if report_filter.project_id:
        from app.auth import check_project_access
        check_project_access(current_user, report_filter.project_id, db)
    
    # Generate report data
    generator = ReportGenerator()
    
    report_data = []
    if report_type == "material-wise":
        report_data = generator.generate_material_wise_report(
            db, report_filter.project_id, report_filter.start_date, report_filter.end_date
        )
    elif report_type == "supplier-wise":
        report_data = generator.generate_supplier_wise_report(
            db, report_filter.project_id, report_filter.supplier_name,
            report_filter.start_date, report_filter.end_date
        )
    elif report_type == "supplier-summary":
        report_data = generator.generate_supplier_summary_report(db, report_filter.project_id)
    elif report_type == "period":
        if not report_filter.site_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Site ID is required for period reports"
            )
        if not report_filter.start_date or not report_filter.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date and end date are required for period reports"
            )
        report_data = generator.generate_period_report(
            db, report_filter.site_id, report_filter.start_date, report_filter.end_date,
            report_filter.material_id
        )
    elif report_type == "stock-valuation":
        report_data = generator.generate_stock_valuation_report(
            db, report_filter.site_id, report_filter.project_id
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type: {report_type}"
        )
    
    # Export to Excel
    return generator.export_to_excel(report_data, report_type)
