"""
File uploads router
"""

# Add to any router file if these imports are missing
from app.auth import check_project_access
from app.auth import get_admin_user_dependency  # Add this function if missing
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
import logging
from app import models
from app.database import get_db
from app.dependencies import (
    get_current_user_dependency,
    log_audit_action,
    validate_project_access
)
from app.utils.excel_processor import ExcelProcessor

router = APIRouter(prefix="/uploads", tags=["uploads"])
logger = logging.getLogger(__name__)

@router.post("/stock")
async def upload_stock_entries(
    file: UploadFile = File(...),
    site_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Upload stock entries from Excel/CSV file
    """
    logger.info(f"Uploading stock entries file: {file.filename} for site {site_id} by {current_user.username}")
    
    # Get site and check project access
    from app.auth import check_project_access
    from app import crud
    
    site = crud.crud_site.get(db, id=site_id)
    if not site:
        logger.warning(f"Site not found: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    check_project_access(current_user, site.project_id, db)
    
    # Validate file
    is_valid, error_msg = ExcelProcessor.validate_file(file)
    if not is_valid:
        logger.error(f"File validation failed: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Process file
    processor = ExcelProcessor()
    results = processor.process_stock_entry_file(db, file, site_id, current_user.id)
    
    logger.info(f"Stock file processing completed: {results['rows_successful']} successful, {results['rows_failed']} failed")
    
    return results

@router.post("/materials")
async def upload_materials(
    file: UploadFile = File(...),
    update_existing: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Upload materials from Excel/CSV file (Alias for /products/upload/materials)
    """
    logger.info(f"Uploading materials file via uploads endpoint: {file.filename} by {current_user.username}")
    
    # Validate file
    is_valid, error_msg = ExcelProcessor.validate_file(file)
    if not is_valid:
        logger.error(f"File validation failed: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Process file
    processor = ExcelProcessor()
    results = processor.process_material_file(db, file, update_existing)
    
    logger.info(f"Materials file processing completed: {results['rows_successful']} successful, {results['rows_failed']} failed")
    
    return results

@router.get("/template")
async def download_upload_template(
    template_type: str = "materials"
):
    """
    Download Excel template for uploads
    """
    logger.debug(f"Downloading {template_type} template")
    
    processor = ExcelProcessor()
    
    if template_type == "materials":
        template_bytes = processor.generate_material_template()
        filename = "material_upload_template.xlsx"
    elif template_type == "stock":
        # Generate stock template (to be implemented)
        template_bytes = processor.generate_material_template()  # Temporary
        filename = "stock_entry_template.xlsx"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template type: {template_type}"
        )
    
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    
    return StreamingResponse(
        BytesIO(template_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
