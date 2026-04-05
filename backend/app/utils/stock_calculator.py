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
            
        # 1. Fetch the entire ledger up to as_of_date in a single, fast query
        all_entries = db.query(models.StockEntry).filter(
            and_(
                models.StockEntry.site_id == site_id,
                models.StockEntry.material_id == material_id,
                models.StockEntry.entry_date <= as_of_date
            )
        ).all()
        
        all_time_received = Decimal('0.00')
        all_time_used = Decimal('0.00')
        
        # 2. Calculate the absolute True Current Balance
        for entry in all_entries:
            if entry.entry_type in [schemas.StockEntryType.RECEIVED.value, schemas.StockEntryType.RETURNED_RECEIVED.value]:
                all_time_received += entry.quantity
            elif entry.entry_type in [schemas.StockEntryType.USED.value, schemas.StockEntryType.RETURNED_SUPPLIER.value]:
                all_time_used += entry.quantity
                
        current_balance = all_time_received - all_time_used
        
        # 3. Calculate Opening Balance (Everything up to 23:59:59 of yesterday)
        yesterday_end = datetime.combine((as_of_date - timedelta(days=1)).date(), datetime.max.time())
        opening_balance = Decimal('0.00')
        
        for entry in all_entries:
            # FIX: Strip timezone from DB date so Python can compare safely
            safe_date = entry.entry_date.replace(tzinfo=None) if getattr(entry.entry_date, 'tzinfo', None) else entry.entry_date
            
            if safe_date <= yesterday_end:
                if entry.entry_type in [schemas.StockEntryType.RECEIVED.value, schemas.StockEntryType.RETURNED_RECEIVED.value]:
                    opening_balance += entry.quantity
                elif entry.entry_type in [schemas.StockEntryType.USED.value, schemas.StockEntryType.RETURNED_SUPPLIER.value]:
                    opening_balance -= entry.quantity

        # 4. Calculate strictly Today's Activity
        today_start = datetime.combine(as_of_date.date(), datetime.min.time())
        today_end = datetime.combine(as_of_date.date(), datetime.max.time())
        
        today_received = Decimal('0.00')
        today_used = Decimal('0.00')
        today_return_received = Decimal('0.00')
        today_return_supplier = Decimal('0.00')
        
        for entry in all_entries:
            # FIX: Strip timezone from DB date so Python can compare safely
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
                    
        # Total IN and OUT for the current day
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
            
            # Compatibility fields for legacy daily report generator
            "today_raw_received": today_received,
            "today_raw_used": today_used,
            "total_return_received": today_return_received,
            "total_return_supplier": today_return_supplier,
            "total_moved": Decimal('0.00'), 
            "total_received_today": total_in_today
        }
        
        logger.debug(f"Stock calculation result: {result}")
        return result
    
    @staticmethod
    def generate_daily_report(
        db: Session,
        site_id: int,
        report_date: date
    ) -> List[models.DailyStockReport]:
        """
        Generate daily stock reports for all materials at a site
        """
        logger.info(f"Generating daily report for site {site_id} on {report_date}")
        
        reports = []
        
        # Get all materials with activity at this site
        materials_query = db.query(models.Material).join(models.StockEntry).filter(
            models.StockEntry.site_id == site_id
        ).distinct()
        
        materials = materials_query.all()
        
        for material in materials:
            # Calculate balance for this material
            as_of_datetime = datetime.combine(report_date, datetime.max.time())
            balance = StockCalculator.calculate_balance(
                db, site_id, material.id, as_of_datetime
            )
            
            # Get previous day's report for opening stock
            previous_date = report_date - timedelta(days=1)
            previous_report = crud.crud_daily_report.get_latest_report(
                db, site_id, material.id
            )
            
            opening_stock = Decimal('0.00')
            if previous_report and previous_report.report_date.date() == previous_date:
                opening_stock = previous_report.closing_stock
            
            # Get today's transactions
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
            
            # Calculate daily totals
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
            
            # Calculate closing stock
            closing_stock = (
                opening_stock +
                daily_received -
                daily_used +
                daily_return_received -
                daily_return_supplier
            )
            
            total_received_today = daily_received - daily_used + daily_return_received
            
            # Create daily report
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
        
        logger.info(f"Generated {len(reports)} daily reports for site {site_id}")
        
        return reports
    
    @staticmethod
    def get_site_stock_summary(
        db: Session,
        site_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Get stock summary for all materials at a site.
        If dates are provided, generates a historical snapshot for that specific date range.
        """
        logger.debug(f"Getting stock summary for site {site_id}, dates: {start_date} to {end_date}")
        
        summary = []
        
        materials_query = db.query(models.Material).join(models.StockEntry).filter(
            models.StockEntry.site_id == site_id
        ).distinct()
        
        materials = materials_query.all()
        
        for material in materials:
            if start_date and end_date:
                # --- DATE RANGE MODE ---
                # 1. Calculate the opening balance (state of the inventory strictly BEFORE start_date)
                start_dt = datetime.combine(start_date, datetime.min.time())
                opening_dt = start_dt - timedelta(microseconds=1)
                
                opening_calc = StockCalculator.calculate_balance(db, site_id, material.id, opening_dt)
                opening_bal = opening_calc["current_balance"]
                
                # 2. Sum up transactions strictly WITHIN the date range
                end_dt = datetime.combine(end_date, datetime.max.time())
                
                all_entries = db.query(models.StockEntry).filter(
                    models.StockEntry.site_id == site_id,
                    models.StockEntry.material_id == material.id
                ).all()
                
                range_received = Decimal('0.00')
                range_used = Decimal('0.00')
                latest_entry_date = None
                
                for e in all_entries:
                    # Strip timezone for safe comparison
                    safe_date = e.entry_date.replace(tzinfo=None) if getattr(e.entry_date, 'tzinfo', None) else e.entry_date
                    
                    if start_dt <= safe_date <= end_dt:
                        # Track the most recent transaction inside this date window
                        if latest_entry_date is None or safe_date > latest_entry_date:
                            latest_entry_date = safe_date
                            
                        if e.entry_type in [schemas.StockEntryType.RECEIVED.value, schemas.StockEntryType.RETURNED_RECEIVED.value]:
                            range_received += e.quantity
                        elif e.entry_type in [schemas.StockEntryType.USED.value, schemas.StockEntryType.RETURNED_SUPPLIER.value]:
                            range_used += e.quantity
                            
                # 3. Calculate Closing Balance at the end of the range
                current_bal = opening_bal + range_received - range_used
                
                summary.append({
                    "material_id": material.id,
                    "material_name": material.name,
                    "category": material.category.name if material.category else "N/A",
                    "unit": material.unit or "N/A",
                    "current_balance": current_bal,
                    "opening_balance": opening_bal,
                    "total_received": range_received,
                    "total_used": range_used,
                    "has_negative_balance": current_bal < Decimal('0.00'),
                    "last_updated": latest_entry_date
                })
            else:
                # --- ALL-TIME LATEST MODE (Used by Summary Cards) ---
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
        logger.debug(f"Validating stock entry: site={site_id}, material={material_id}, type={entry_type}, qty={quantity}")
        if entry_type == schemas.StockEntryType.USED.value:
            current_balance = StockCalculator.calculate_balance(
                db, site_id, material_id
            )["current_balance"]
            
            if current_balance < quantity:
                logger.warning(f"Insufficient stock for usage. Balance: {current_balance}, Requested: {quantity}")
        return True

def cli_calculate_stock(db: Session, site_id: int, material_id: int):
    print(f"🧮 Calculating stock balance for site {site_id}, material {material_id}")
    calculator = StockCalculator()
    result = calculator.calculate_balance(db, site_id, material_id)
    
    print("📊 Stock Balance Result:")
    print(f"  📦 Material ID: {result['material_id']}")
    print(f"  🏢 Site ID: {result['site_id']}")
    print(f"  📅 As of Date: {result['as_of_date']}")
    print(f"  📈 Opening Balance: {result['opening_balance']}")
    print(f"  📥 Total Received: {result['total_received']}")
    print(f"  📤 Total Used: {result['total_used']}")
    print(f"  📊 Current Balance: {result['current_balance']}")
    
    if result['has_negative_balance']:
        print("  ⚠️  WARNING: Negative balance detected!")
    
    return result

def cli_generate_daily_report(db: Session, site_id: int, report_date: date):
    print(f"📋 Generating daily report for site {site_id} on {report_date}")
    calculator = StockCalculator()
    reports = calculator.generate_daily_report(db, site_id, report_date)
    print(f"✅ Generated {len(reports)} daily reports")
    return reports
