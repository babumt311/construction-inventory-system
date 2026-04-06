"""
Stock calculation utilities
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import logging
from app import models, schemas, crud

logger = logging.getLogger(__name__)

class StockCalculator:
    """Stock calculation engine"""
    
    @staticmethod
    def calculate_balance(
        db: Session,
        site_id: int,
        material_id: int,
        as_of_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        logger.debug(f"Calculating stock balance for site {site_id}, material {material_id}")
        
        if not as_of_date:
            as_of_date = datetime.now()
            
        as_of_date = as_of_date.replace(tzinfo=None) if getattr(as_of_date, 'tzinfo', None) else as_of_date
            
        all_entries = db.query(models.StockEntry).filter(
            and_(
                models.StockEntry.site_id == site_id,
                models.StockEntry.material_id == material_id,
                models.StockEntry.entry_date <= as_of_date
            )
        ).all()
        
        all_time_received = Decimal('0.00')
        all_time_used = Decimal('0.00')
        
        for entry in all_entries:
            if entry.entry_type in [schemas.StockEntryType.RECEIVED.value, schemas.StockEntryType.RETURNED_RECEIVED.value]:
                all_time_received += entry.quantity
            elif entry.entry_type in [schemas.StockEntryType.USED.value, schemas.StockEntryType.RETURNED_SUPPLIER.value]:
                all_time_used += entry.quantity
                
        current_balance = all_time_received - all_time_used
        
        yesterday_end = datetime.combine((as_of_date - timedelta(days=1)).date(), datetime.max.time())
        opening_balance = Decimal('0.00')
        
        for entry in all_entries:
            safe_date = entry.entry_date.replace(tzinfo=None) if getattr(entry.entry_date, 'tzinfo', None) else entry.entry_date
            
            if safe_date <= yesterday_end:
                if entry.entry_type in [schemas.StockEntryType.RECEIVED.value, schemas.StockEntryType.RETURNED_RECEIVED.value]:
                    opening_balance += entry.quantity
                elif entry.entry_type in [schemas.StockEntryType.USED.value, schemas.StockEntryType.RETURNED_SUPPLIER.value]:
                    opening_balance -= entry.quantity

        today_start = datetime.combine(as_of_date.date(), datetime.min.time())
        today_end = datetime.combine(as_of_date.date(), datetime.max.time())
        
        today_received = Decimal('0.00')
        today_used = Decimal('0.00')
        today_return_received = Decimal('0.00')
        today_return_supplier = Decimal('0.00')
        
        for entry in all_entries:
            safe_date = entry.entry_date.replace(tzinfo=None) if getattr(entry.entry_date, 'tzinfo', None) else entry.entry_date
            
            if today_start <= safe_date <= today_end:
                if entry.entry_type == schemas.StockEntryType.RECEIVED.value:
                    today_received += entry.quantity
                elif entry.entry_type == schemas.StockEntryType.USED.value:
                    today_used += entry.quantity
                elif entry.entry_type == schemas.StockEntryType.RETURNED_RECEIVED.value:
                    today_return_received += entry.quantity
                elif entry.entry_type == schemas.StockEntryType.RETURNED_SUPPLIER.value:
                    today_return_supplier += entry.quantity
                    
        # Explicitly separate out "Used" and "Returned"
        result = {
            "material_id": material_id,
            "site_id": site_id,
            "as_of_date": as_of_date,
            "opening_balance": opening_balance,
            "total_received": today_received, 
            "total_used": today_used, 
            "total_returned_supplier": today_return_supplier,
            "total_returned_received": today_return_received,
            "current_balance": current_balance,
            "has_negative_balance": current_balance < Decimal('0.00')
        }
        
        return result
    
    @staticmethod
    def get_site_stock_summary(
        db: Session,
        site_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        summary = []
        
        materials = db.query(models.Material).join(models.StockEntry).filter(
            models.StockEntry.site_id == site_id
        ).distinct().all()
        
        if start_date or end_date:
            effective_start = start_date if start_date else date.min
            effective_end = end_date if end_date else date.today()
            start_dt = datetime.combine(effective_start, datetime.min.time())
            end_dt = datetime.combine(effective_end, datetime.max.time())
            
            for material in materials:
                entries_in_range = db.query(models.StockEntry).filter(
                    models.StockEntry.site_id == site_id,
                    models.StockEntry.material_id == material.id,
                    models.StockEntry.entry_date >= start_dt,
                    models.StockEntry.entry_date <= end_dt
                ).order_by(models.StockEntry.entry_date.asc()).all()
                
                if not entries_in_range:
                    calc = StockCalculator.calculate_balance(db, site_id, material.id, end_dt)
                    actual_last_date = db.query(func.max(models.StockEntry.entry_date)).filter(
                        models.StockEntry.site_id == site_id,
                        models.StockEntry.material_id == material.id,
                        models.StockEntry.entry_date <= end_dt
                    ).scalar()
                    
                    summary.append({
                        "material_id": material.id,
                        "material_name": material.name,
                        "category": material.category.name if material.category else "N/A",
                        "unit": material.unit or "N/A",
                        "current_balance": calc["current_balance"],
                        "opening_balance": calc["current_balance"],
                        "total_received": Decimal('0.00'),
                        "total_used": Decimal('0.00'),
                        "total_returned_supplier": Decimal('0.00'),
                        "has_negative_balance": calc["current_balance"] < 0,
                        "last_updated": actual_last_date
                    })
                    continue
                
                entries_by_date = {}
                for e in entries_in_range:
                    safe_date = e.entry_date.replace(tzinfo=None) if getattr(e.entry_date, 'tzinfo', None) else e.entry_date
                    d_key = safe_date.date()
                    if d_key not in entries_by_date:
                        entries_by_date[d_key] = []
                    entries_by_date[d_key].append((e, safe_date))
                    
                for d_key, daily_data in entries_by_date.items():
                    day_start = datetime.combine(d_key, datetime.min.time())
                    opening_dt = day_start - timedelta(microseconds=1)
                    
                    opening_calc = StockCalculator.calculate_balance(db, site_id, material.id, opening_dt)
                    opening_bal = opening_calc["current_balance"]
                    
                    day_received = Decimal('0.00')
                    day_used = Decimal('0.00')
                    day_returned_supplier = Decimal('0.00')
                    latest_in_day = None
                    
                    for e, safe_date in daily_data:
                        if latest_in_day is None or safe_date > latest_in_day:
                            latest_in_day = safe_date
                            
                        if e.entry_type in [schemas.StockEntryType.RECEIVED.value, schemas.StockEntryType.RETURNED_RECEIVED.value]:
                            day_received += e.quantity
                        elif e.entry_type == schemas.StockEntryType.USED.value:
                            day_used += e.quantity
                        elif e.entry_type == schemas.StockEntryType.RETURNED_SUPPLIER.value:
                            day_returned_supplier += e.quantity
                            
                    closing_bal = opening_bal + day_received - day_used - day_returned_supplier
                    
                    summary.append({
                        "material_id": material.id,
                        "material_name": material.name,
                        "category": material.category.name if material.category else "N/A",
                        "unit": material.unit or "N/A",
                        "current_balance": closing_bal,
                        "opening_balance": opening_bal,
                        "total_received": day_received,
                        "total_used": day_used,
                        "total_returned_supplier": day_returned_supplier,
                        "has_negative_balance": closing_bal < 0,
                        "last_updated": latest_in_day
                    })
        else:
            for material in materials:
                balance = StockCalculator.calculate_balance(db, site_id, material.id)
                latest_entry_date = db.query(func.max(models.StockEntry.entry_date)).filter(
                    models.StockEntry.site_id == site_id,
                    models.StockEntry.material_id == material.id
                ).scalar()
                
                summary.append({
                    "material_id": material.id,
                    "material_name": material.name,
                    "category": material.category.name if material.category else "N/A",
                    "unit": material.unit or "N/A",
                    "current_balance": balance["current_balance"],
                    "opening_balance": balance["opening_balance"],
                    "total_received": balance["total_received"],
                    "total_used": balance["total_used"],
                    "total_returned_supplier": balance["total_returned_supplier"],
                    "has_negative_balance": balance["has_negative_balance"],
                    "last_updated": latest_entry_date 
                })
        
        return summary
    
    @staticmethod
    def validate_stock_entry(
        db: Session,
        site_id: int,
        material_id: int,
        entry_type: str,
        quantity: Decimal
    ) -> bool:
        if entry_type == schemas.StockEntryType.USED.value or entry_type == schemas.StockEntryType.RETURNED_SUPPLIER.value:
            calc_result = StockCalculator.calculate_balance(db, site_id, material_id)
            current_balance = calc_result["current_balance"]
            
            if current_balance < quantity:
                logger.warning(f"Insufficient stock. Balance: {current_balance}, Requested: {quantity}")
        return True
