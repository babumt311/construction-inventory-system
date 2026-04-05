"""
Stock calculation utilities
"""
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
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
        """
        Calculate true current stock balance for a material at a site.
        """
        logger.debug(f"Calculating stock balance for site {site_id}, material {material_id}")
        
        if not as_of_date:
            as_of_date = datetime.now()
            
        # Strip timezone from as_of_date just to be safe for local python math
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
                    
        total_in_today = today_received + today_return_received
        total_out_today = today_used + today_return_supplier
                
        result = {
            "material_id": material_id,
            "site_id": site_id,
            "as_of_date": as_of_date,
            "opening_balance": opening_balance,
            "total_received": total_in_today,
            "total_used": total_out_today,
            "current_balance": current_balance,
            "has_negative_balance": current_balance < Decimal('0.00'),
            
            "today_raw_received": today_received,
            "today_raw_used": today_used,
            "total_return_received": today_return_received,
            "total_return_supplier": today_return_supplier,
            "total_moved": Decimal('0.00'), 
            "total_received_today": total_in_today
        }
        
        return result
    
    @staticmethod
    def generate_daily_report(
        db: Session,
        site_id: int,
        report_date: date
    ) -> List[models.DailyStockReport]:
        logger.info(f"Generating daily report for site {site_id} on {report_date}")
        reports = []
        
        materials_query = db.query(models.Material).join(models.StockEntry).filter(
            models.StockEntry.site_id == site_id
        ).distinct()
        
        materials = materials_query.all()
        
        for material in materials:
            as_of_datetime = datetime.combine(report_date, datetime.max.time())
            
            previous_date = report_date - timedelta(days=1)
            previous_report = crud.crud_daily_report.get_latest_report(
                db, site_id, material.id
            )
            
            opening_stock = Decimal('0.00')
            if previous_report and previous_report.report_date.date() == previous_date:
                opening_stock = previous_report.closing_stock
            
            today_start = datetime.combine(report_date, datetime.min.time())
            today_end = datetime.combine(report_date, datetime.max.time())
            
            today_entries = db.query(models.StockEntry).filter(
                and_(
                    models.StockEntry.site_id == site_id,
                    models.StockEntry.material_id == material.id,
                    models.StockEntry.entry_date >= today_start,
                    models.StockEntry.entry_date <= today_end
                )
            ).all()
            
            daily_received = Decimal('0.00')
            daily_used = Decimal('0.00')
            daily_return_received = Decimal('0.00')
            daily_return_supplier = Decimal('0.00')
            
            for entry in today_entries:
                if entry.entry_type == schemas.StockEntryType.RECEIVED.value:
                    daily_received += entry.quantity
                elif entry.entry_type == schemas.StockEntryType.USED.value:
                    daily_used += entry.quantity
                elif entry.entry_type == schemas.StockEntryType.RETURNED_RECEIVED.value:
                    daily_return_received += entry.quantity
                elif entry.entry_type == schemas.StockEntryType.RETURNED_SUPPLIER.value:
                    daily_return_supplier += entry.quantity
            
            closing_stock = (
                opening_stock +
                daily_received -
                daily_used +
                daily_return_received -
                daily_return_supplier
            )
            
            total_received_today = daily_received - daily_used + daily_return_received
            
            report = models.DailyStockReport(
                site_id=site_id,
                material_id=material.id,
                report_date=today_end,
                opening_stock=opening_stock,
                received=daily_received,
                used=daily_used,
                returned_received=daily_return_received,
                returned_supplier=daily_return_supplier,
                closing_stock=closing_stock,
                total_received=total_received_today
            )
            
            db.add(report)
            reports.append(report)
        
        db.commit()
        return reports
    
    @staticmethod
    def get_site_stock_summary(
        db: Session,
        site_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Get stock summary for all materials.
        If dates are provided, dynamically generates a DAY-BY-DAY ledger!
        """
        summary = []
        
        materials = db.query(models.Material).join(models.StockEntry).filter(
            models.StockEntry.site_id == site_id
        ).distinct().all()
        
        if start_date or end_date:
            # --- DATE RANGED DAILY LEDGER MODE ---
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
                
                # If no activity in this range, just show the static balance
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
                        "has_negative_balance": calc["current_balance"] < 0,
                        "last_updated": actual_last_date
                    })
                    continue
                
                # Group entries by exact Day
                entries_by_date = {}
                for e in entries_in_range:
                    safe_date = e.entry_date.replace(tzinfo=None) if getattr(e.entry_date, 'tzinfo', None) else e.entry_date
                    d_key = safe_date.date()
                    if d_key not in entries_by_date:
                        entries_by_date[d_key] = []
                    entries_by_date[d_key].append((e, safe_date))
                    
                # Generate a separate row for EACH active day
                for d_key, daily_data in entries_by_date.items():
                    day_start = datetime.combine(d_key, datetime.min.time())
                    opening_dt = day_start - timedelta(microseconds=1)
                    
                    opening_calc = StockCalculator.calculate_balance(db, site_id, material.id, opening_dt)
                    opening_bal = opening_calc["current_balance"]
                    
                    day_received = Decimal('0.00')
                    day_used = Decimal('0.00')
                    latest_in_day = None
                    
                    for e, safe_date in daily_data:
                        if latest_in_day is None or safe_date > latest_in_day:
                            latest_in_day = safe_date
                            
                        if e.entry_type in [schemas.StockEntryType.RECEIVED.value, schemas.StockEntryType.RETURNED_RECEIVED.value]:
                            day_received += e.quantity
                        elif e.entry_type in [schemas.StockEntryType.USED.value, schemas.StockEntryType.RETURNED_SUPPLIER.value]:
                            day_used += e.quantity
                            
                    closing_bal = opening_bal + day_received - day_used
                    
                    summary.append({
                        "material_id": material.id,
                        "material_name": material.name,
                        "category": material.category.name if material.category else "N/A",
                        "unit": material.unit or "N/A",
                        "current_balance": closing_bal,
                        "opening_balance": opening_bal,
                        "total_received": day_received,
                        "total_used": day_used,
                        "has_negative_balance": closing_bal < 0,
                        "last_updated": latest_in_day
                    })
        else:
            # --- ALL-TIME LATEST MODE (Used by Summary Cards) ---
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
        if entry_type == schemas.StockEntryType.USED.value:
            current_balance = StockCalculator.calculate_balance(
                db
