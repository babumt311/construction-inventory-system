"""
Stock management router
"""

import time
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
from app.utils.logger import log_activity

router = APIRouter(prefix="/stock", tags=["stock"])
logger = logging.getLogger(__name__)

# Cache dictionary to prevent log spamming when fetching multiple sites
REPORT_LOG_CACHE = {}

@router.post("/entries", response_model=schemas.StockEntryInDB)
async def create_stock_entry(
    stock_in: schemas.StockEntryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    
    site = crud.crud_site.get(db, id=stock_in.site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    check_project_access(current_user, site.project_id, db)

    material = crud.crud_material.get(db, id=stock_in.material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    calculator = StockCalculator()
    if not calculator.validate_stock_entry(db, stock_in.site_id, stock_in.material_id, stock_in.entry_type, stock_in.quantity):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stock entry validation failed")

    stock_data = stock_in.dict()
    stock_data["created_by"] = current_user.id

    if "reference_no" in stock_data:
        if stock_data["reference_no"]:
            stock_data["invoice_no"] = stock_data["reference_no"]
        stock_data.pop("reference_no")

    stock_data["unit_cost"] = stock_in.unit_cost or material.standard_cost or Decimal('0.00')
    stock_data["tax_percent"] = stock_in.tax_percent or Decimal('0.00')
    stock_data["tax_amount"] = stock_in.tax_amount or Decimal('0.00')
    stock_data["total_cost"] = stock_in.total_cost or (stock_data["unit_cost"] * Decimal(str(stock_in.quantity)))

    stock_entry = models.StockEntry(**stock_data)
    db.add(stock_entry)

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

    db.commit()
    db.refresh(stock_entry)
    
    # SYSTEM LOGGING (Capitalized entry type for better readability)
    log_activity(
        db, 
        current_user.username, 
        "Stock Entry", 
        f"Recorded '{stock_entry.entry_type.upper()}' of {stock_entry.quantity} units for Material '{material.name}' at Site '{site.name}'."
    )
    
    return stock_entry

@router.get("/entries", response_model=List[schemas.StockEntryInDB])
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
    
    query = db.query(models.StockEntry)
    
    if site_id:
        site = crud.crud_site.get(db, id=site_id)
        if site:
            try:
                check_project_access(current_user, site.project_id, db)
            except HTTPException:
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
    
    if pagination.sort_by:
        if hasattr(models.StockEntry, pagination.sort_by):
            if pagination.sort_order == "desc":
                query = query.order_by(getattr(models.StockEntry, pagination.sort_by).desc())
            else:
                query = query.order_by(getattr(models.StockEntry, pagination.sort_by).asc())
    else:
        query = query.order_by(models.StockEntry.entry_date.desc())
    
    return query.offset(pagination.skip).limit(pagination.size).all()

@router.get("/entries/{entry_id}", response_model=schemas.StockEntryInDB)
async def read_stock_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    entry = crud.crud_stock_entry.get(db, id=entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock entry not found")
    
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
    
    entry = crud.crud_stock_entry.get(db, id=entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock entry not found")
    
    site = crud.crud_site.get(db, id=entry.site_id)
    if site:
        check_project_access(current_user, site.project_id, db)
    
    if entry.created_by != current_user.id and current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.OWNER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this entry")
    
    update_data = stock_in.dict(exclude_unset=True)
    
    if "quantity" in update_data:
        new_qty = Decimal(str(update_data["quantity"]))
        historical_price = entry.unit_cost or Decimal('0.00')
        update_data["total_cost"] = historical_price * new_qty
    
    for field, value in update_data.items():
        if hasattr(entry, field):
            setattr(entry, field, value)
    
    db.add(entry)
    db.commit()
    db.refresh(entry)

    material = crud.crud_material.get(db, id=entry.material_id)
    mat_name = material.name if material else f"ID {entry.material_id}"
    site_name = site.name if site else "Unknown Site"
    
    # SYSTEM LOGGING
    log_activity(
        db, 
        current_user.username, 
        "Stock Update", 
        f"Updated '{entry.entry_type.upper()}' entry to {entry.quantity} units for Material '{mat_name}' at Site '{site_name}'."
    )
    
    return entry

@router.delete("/entries/{entry_id}")
async def delete_stock_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.OWNER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires admin or owner role")
    
    entry = crud.crud_stock_entry.get(db, id=entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock entry not found")
        
    site = crud.crud_site.get(db, id=entry.site_id)
    material = crud.crud_material.get(db, id=entry.material_id)
    site_name = site.name if site else "Unknown Site"
    mat_name = material.name if material else "Unknown Material"
    qty = entry.quantity
    e_type = entry.entry_type

    crud.crud_stock_entry.delete(db, id=entry_id)
    
    # SYSTEM LOGGING
    log_activity(
        db, 
        current_user.username, 
        "Stock Deletion", 
        f"Deleted '{e_type.upper()}' entry of {qty} units for Material '{mat_name}' at Site '{site_name}'."
    )
    
    return {"message": "Stock entry deleted successfully"}

@router.get("/balance/{site_id}/{material_id}")
async def get_stock_balance(
    site_id: int,
    material_id: int,
    as_of_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    site = crud.crud_site.get(db, id=site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    
    check_project_access(current_user, site.project_id, db)
    calculator = StockCalculator()
    balance = calculator.calculate_balance(db, site_id, material_id, as_of_date)
    
    material = crud.crud_material.get(db, id=material_id)
    if material:
        balance["material_name"] = material.name
        balance["unit"] = material.unit
    
    return balance

@router.get("/site-summary/{site_id}")
async def get_site_stock_summary(
    site_id: int,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    supplier_name: Optional[str] = Query(None), 
    entry_type: Optional[str] = Query(None),    
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    site = crud.crud_site.get(db, id=site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    
    check_project_access(current_user, site.project_id, db)
    calculator = StockCalculator()
    summary = calculator.get_site_stock_summary(db, site_id, start_date, end_date, supplier_name, entry_type)
    
    # NEW: DEBOUNCED LOGGING (Logs only once every 30 seconds per user, prevents spam!)
    current_time = time.time()
    cache_key = f"{current_user.id}_report_pull"
    
    if current_time - REPORT_LOG_CACHE.get(cache_key, 0) > 30:
        log_activity(
            db, 
            current_user.username, 
            "Report Generated", 
            "Pulled comprehensive Stock Ledger & Balances report."
        )
        REPORT_LOG_CACHE[cache_key] = current_time
    
    return summary

@router.post("/generate-daily-report/{site_id}")
async def generate_daily_stock_report(
    site_id: int,
    report_date: date = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    
    if current_user.role not in [schemas.UserRole.ADMIN, schemas.UserRole.OWNER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires admin or owner role")
    
    site = crud.crud_site.get(db, id=site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    
    if not report_date:
        report_date = date.today()
    
    calculator = StockCalculator()
    reports = calculator.generate_daily_report(db, site_id, report_date)
    
    log_activity(db, current_user.username, "Report Generation", f"Generated {len(reports)} daily stock reports for Site '{site.name}'.")
    
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
    site = crud.crud_site.get(db, id=site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    
    check_project_access(current_user, site.project_id, db)
    query = db.query(models.DailyStockReport).filter(models.DailyStockReport.site_id == site_id)
    
    if report_date:
        start_of_day = datetime.combine(report_date, datetime.min.time())
        end_of_day = datetime.combine(report_date, datetime.max.time())
        query = query.filter(models.DailyStockReport.report_date.between(start_of_day, end_of_day))
    
    if material_id:
        query = query.filter(models.DailyStockReport.material_id == material_id)
    
    query = query.order_by(models.DailyStockReport.report_date.desc(), models.DailyStockReport.material_id.asc())
    return query.offset(pagination.skip).limit(pagination.size).all()
