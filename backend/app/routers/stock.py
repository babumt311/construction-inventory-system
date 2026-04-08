"""
Stock management router
"""

from app.auth import check_project_access
from typing import Any, List, Optional
from datetime import datetime, date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging
from app import schemas, crud, models
from app.database import get_db
from app.dependencies import (
    get_current_user_dependency,
    PaginationParams,
    log_audit_action
)
from app.utils.stock_calculator import StockCalculator

router = APIRouter(prefix="/stock", tags=["stock"])
logger = logging.getLogger(__name__)

@router.post("/entries", response_model=schemas.StockEntryInDB)
async def create_stock_entry(
    stock_in: schemas.StockEntryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Create new stock entry, lock in historical costs, and update total balance
    """

    # 1. Create stock entry history with IMMUTABLE COSTS
    stock_data = stock_in.dict()
    stock_data["created_by"] = current_user.id
    
    # --- ENTERPRISE LEDGER PROTOCOL: USE FRONTEND DYNAMIC COST ---
    # Stop overwriting with standard_cost. Save the values exactly as entered in UI.
    stock_data["unit_cost"] = stock_in.unit_cost or Decimal('0.00')
    stock_data["tax_percent"] = stock_in.tax_percent or Decimal('0.00')
    stock_data["tax_amount"] = stock_in.tax_amount or Decimal('0.00')
    stock_data["total_cost"] = stock_in.total_cost or Decimal('0.00')
    
    # Map the frontend's 'reference_no' directly into the 'invoice_no' column
    if hasattr(stock_in, 'reference_no') and stock_in.reference_no:
        stock_data["invoice_no"] = stock_in.reference_no
        
    # Remove reference_no from dictionary so SQLAlchemy doesn't crash looking for it
    stock_data.pop("reference_no", None)
    # ---------------------------------------------------------
    
    stock_entry = models.StockEntry(**stock_data)
    db.add(stock_entry)
    logger.info(f"Creating stock entry by user: {current_user.username}")
    
    # Check if user has access to the site's project
    site = crud.crud_site.get(db, id=stock_in.site_id)
    if not site:
        logger.warning(f"Site not found: {stock_in.site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # Validate project access
    check_project_access(current_user, site.project_id, db)
    
    # Validate material exists
    material = crud.crud_material.get(db, id=stock_in.material_id)
    if not material:
        logger.warning(f"Material not found: {stock_in.material_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    # Validate stock entry
    calculator = StockCalculator()
    if not calculator.validate_stock_entry(
        db, stock_in.site_id, stock_in.material_id, stock_in.entry_type, stock_in.quantity
    ):
        logger.warning(f"Stock entry validation failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock entry validation failed"
        )
    
    # 1. Create stock entry history with IMMUTABLE COSTS
    stock_data = stock_in.dict()
    stock_data["created_by"] = current_user.id
    
    # --- ENTERPRISE LEDGER PROTOCOL: LOCK IN CURRENT PRICE ---
    current_unit_price = material.standard_cost or Decimal('0.00')
    stock_data["unit_cost"] = current_unit_price
    stock_data["total_cost"] = current_unit_price * Decimal(str(stock_in.quantity))
    # ---------------------------------------------------------
    
    stock_entry = models.StockEntry(**stock_data)
    db.add(stock_entry)

    # 2. Update the Stock Balance Summary Table
    try:
        balance = db.query(models.StockBalance).filter(
            models.StockBalance.site_id == stock_in.site_id,
            models.StockBalance.material_id == stock_in.material_id
        ).first()

        qty_change = stock_in.quantity if stock_in.entry_type in ['received', 'returned_received'] else -stock_in.quantity

        if balance:
            balance.current_balance += qty_change
            if qty_change > 0:
                balance.total_received += qty_change
            else:
                balance.total_used += abs(qty_change)
        else:
            new_balance = models.StockBalance(
                site_id=stock_in.site_id,
                material_id=stock_in.material_id,
                current_balance=qty_change,
                opening_balance=0,
                total_received=qty_change if qty_change > 0 else 0,
                total_used=abs(qty_change) if qty_change < 0 else 0
            )
            db.add(new_balance)
    except Exception as e:
        logger.warning(f"StockBalance update skipped (Handled by calculator): {e}")

    # 3. Permanently Commit to PostgreSQL
    db.commit()
    db.refresh(stock_entry)
    
    logger.info(f"Stock entry created: ID {stock_entry.id}, type {stock_entry.entry_type}, qty {stock_entry.quantity}")
    
    return stock_entry

@router.get("/entries/", response_model=List[schemas.StockEntryInDB])
async def read_stock_entries(
    site_id: Optional[int] = Query(None),
    material_id: Optional[int] = Query(None),
    entry_type: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Retrieve stock entries with filtering
    """
    logger.debug(f"Reading stock entries by user: {current_user.username}")
    
    query = db.query(models.StockEntry)
    
    # Apply filters
    if site_id:
        site = crud.crud_site.get(db, id=site_id)
        if site:
            try:
                check_project_access(current_user, site.project_id, db)
            except HTTPException:
                logger.warning(f"User {current_user.id} doesn't have access to site {site_id}")
                return []
        query = query.filter(models.StockEntry.site_id == site_id)
    
    if material_id:
        query = query.filter(models.StockEntry.material_id == material_id)
    
    if entry_type:
        query = query.filter(models.StockEntry.entry_type == entry_type)
    
    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        query = query.filter(models.StockEntry.entry_date >= start_datetime)
    
    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(models.StockEntry.entry_date <= end_datetime)
    
    # Apply sorting
    if pagination.sort_by:
        if hasattr(models.StockEntry, pagination.sort_by):
            if pagination.sort_order == "desc":
                query = query.order_by(getattr(models.StockEntry, pagination.sort_by).desc())
            else:
                query = query.order_by(getattr(models.StockEntry, pagination.sort_by).asc())
    else:
        query = query.order_by(models.StockEntry.entry_date.desc())
    
    # Apply pagination
    entries = query.offset(pagination.skip).limit(pagination.size).all()
    
    logger.debug(f"Returning {len(entries)} stock entries")
    return entries

@router.get("/entries/{entry_id}", response_model=schemas.StockEntryInDB)
async def read_stock_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Get stock entry by ID
    """
    logger.debug(f"Reading stock entry ID: {entry_id}")
    
    entry = crud.crud_stock_entry.get(db, id=entry_id)
    
    if not entry:
        logger.warning(f"Stock entry not found: {entry_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock entry not found"
        )
    
    # Check access to site's project
    site = crud.crud_site.get(db, id=entry.site_id)
    if site:
        check_project_access(current_user, site.project_id, db)
    
    return entry

@router.put("/entries/{entry_id}", response_model=schemas.StockEntryInDB)
async def update_stock_entry(
    entry_id: int,
    stock_in: schemas.StockEntryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Update stock entry
    """
    logger.info(f"Updating stock entry ID: {entry_id} by user: {current_user.username}")
    
    entry = crud.crud_stock_entry.get(db, id=entry_id)
    
    if not entry:
        logger.warning(f"Stock entry not found: {entry_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock entry not found"
        )
    
    # Check access to site's project
    site = crud.crud_site.get(db, id=entry.site_id)
    if site:
        check_project_access(current_user, site.project_id, db)
    
    # Only allow updates by the creator or admin/owner
    if entry.created_by != current_user.id and current_user.role not in [
        schemas.UserRole.ADMIN, schemas.UserRole.OWNER
    ]:
        logger.warning(f"User {current_user.id} not authorized to update entry {entry_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this entry"
        )
    
    # Update entry
    update_data = stock_in.dict(exclude_unset=True)
    
    # --- ENTERPRISE LEDGER PROTOCOL: RECALCULATE COST USING HISTORICAL UNIT PRICE ---
    if "quantity" in update_data:
        new_qty = Decimal(str(update_data["quantity"]))
        historical_price = entry.unit_cost or Decimal('0.00')
        update_data["total_cost"] = historical_price * new_qty
    # --------------------------------------------------------------------------------
    
    for field, value in update_data.items():
        if hasattr(entry, field):
            setattr(entry, field, value)
    
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    logger.info(f"Stock entry updated: ID {entry_id}")
    
    return entry

@router.delete("/entries/{entry_id}")
async def delete_stock_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Delete stock entry (Admin/Owner only)
    """
    logger.info(f"Deleting stock entry ID: {entry_id} by user: {current_user.username}")
    
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.OWNER]:
        logger.warning(f"User {current_user.username} not authorized to delete stock entries")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires admin or owner role"
        )
    
    entry = crud.crud_stock_entry.delete(db, id=entry_id)
    
    if not entry:
        logger.warning(f"Stock entry not found: {entry_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock entry not found"
        )
    
    logger.info(f"Stock entry deleted: ID {entry_id}")
    
    return {"message": "Stock entry deleted successfully"}

@router.get("/balance/{site_id}/{material_id}")
async def get_stock_balance(
    site_id: int,
    material_id: int,
    as_of_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Get current stock balance for a material at a site
    """
    logger.debug(f"Getting stock balance for site {site_id}, material {material_id}")
    
    # Check access to site's project
    site = crud.crud_site.get(db, id=site_id)
    if not site:
        logger.warning(f"Site not found: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    check_project_access(current_user, site.project_id, db)
    
    # Calculate balance
    calculator = StockCalculator()
    balance = calculator.calculate_balance(db, site_id, material_id, as_of_date)
    
    # Get material info
    material = crud.crud_material.get(db, id=material_id)
    if material:
        balance["material_name"] = material.name
        balance["unit"] = material.unit
    
    logger.debug(f"Stock balance calculated: {balance['current_balance']}")
    
    return balance

@router.get("/site-summary/{site_id}")
async def get_site_stock_summary(
    site_id: int,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Get stock summary for all materials at a site within a date range
    """
    logger.debug(f"Getting site stock summary for site: {site_id}, dates: {start_date} to {end_date}")
    
    # Check access to site's project
    site = crud.crud_site.get(db, id=site_id)
    if not site:
        logger.warning(f"Site not found: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    check_project_access(current_user, site.project_id, db)
    
    # Get summary
    calculator = StockCalculator()
    summary = calculator.get_site_stock_summary(db, site_id, start_date, end_date)
    
    logger.debug(f"Returning stock summary with {len(summary)} materials")
    
    return summary

@router.post("/generate-daily-report/{site_id}")
async def generate_daily_stock_report(
    site_id: int,
    report_date: date = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Generate daily stock report for a site
    """
    logger.info(f"Generating daily stock report for site {site_id} by user: {current_user.username}")
    
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.OWNER]:
        logger.warning(f"User {current_user.username} not authorized to generate reports")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires admin or owner role"
        )
    
    # Check access to site's project
    site = crud.crud_site.get(db, id=site_id)
    if not site:
        logger.warning(f"Site not found: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # Use today's date if not specified
    if not report_date:
        report_date = date.today()
    
    # Generate reports
    calculator = StockCalculator()
    reports = calculator.generate_daily_report(db, site_id, report_date)
    
    logger.info(f"Generated {len(reports)} daily reports for site {site_id}")
    
    return {
        "message": f"Generated {len(reports)} daily reports",
        "site_id": site_id,
        "report_date": report_date,
        "report_count": len(reports)
    }

@router.get("/daily-reports/{site_id}")
async def get_daily_reports(
    site_id: int,
    report_date: Optional[date] = Query(None),
    material_id: Optional[int] = Query(None),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Get daily stock reports for a site
    """
    logger.debug(f"Getting daily reports for site: {site_id}")
    
    # Check access to site's project
    site = crud.crud_site.get(db, id=site_id)
    if not site:
        logger.warning(f"Site not found: {site_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    check_project_access(current_user, site.project_id, db)
    
    query = db.query(models.DailyStockReport).filter(
        models.DailyStockReport.site_id == site_id
    )
    
    # Apply filters
    if report_date:
        start_of_day = datetime.combine(report_date, datetime.min.time())
        end_of_day = datetime.combine(report_date, datetime.max.time())
        query = query.filter(
            models.DailyStockReport.report_date.between(start_of_day, end_of_day)
        )
    
    if material_id:
        query = query.filter(models.DailyStockReport.material_id == material_id)
    
    # Apply sorting
    query = query.order_by(
        models.DailyStockReport.report_date.desc(),
        models.DailyStockReport.material_id.asc()
    )
    
    # Apply pagination
    reports = query.offset(pagination.skip).limit(pagination.size).all()
    
    logger.debug(f"Returning {len(reports)} daily reports")
    
    return reports

# CLI endpoints for stock management
@router.get("/cli/calculate/{site_id}/{material_id}")
async def cli_calculate_stock(
    site_id: int,
    material_id: int,
    db: Session = Depends(get_db)
):
    """CLI endpoint to calculate stock balance"""
    print("🧮 CLI Stock Calculation")
    
    calculator = StockCalculator()
    result = calculator.calculate_balance(db, site_id, material_id)
    
    print(f"📊 Stock Balance for Site {site_id}, Material {material_id}:")
    print(f"  📅 As of: {result['as_of_date']}")
    print(f"  📈 Opening Balance: {result['opening_balance']}")
    print(f"  📥 Total Received: {result['total_received']}")
    print(f"  📤 Total Used: {result['total_used']}")
    print(f"  🔄 Return Received: {result.get('total_transfer_in', 0)}")
    print(f"  ↩️  Return to Supplier: {result.get('total_returned_supplier', 0)}")
    print(f"  📊 Current Balance: {result['current_balance']}")
    
    if result['has_negative_balance']:
        print("  ⚠️  WARNING: Negative balance!")
    
    return result
