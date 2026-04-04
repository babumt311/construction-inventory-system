"""
Stock calculation utilities
"""
from datetime import datetime, date, timedelta
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
        Calculate current stock balance for a material at a site
        
        Formula: B = PB + R - U - M + rr - rs
        Where:
          B = Current Balance
          PB = Previous Balance (closing stock of previous day)
          R = Total Received
          U = Total Used
          M = Total Moved
          rr = Total Return Received
          rs = Total Return to Supplier
        """
        logger.debug(f"Calculating stock balance for site {site_id}, material {material_id}")
        
        if not as_of_date:
            as_of_date = datetime.now()
        
        # Get all stock entries up to the specified date
        stock_entries = db.query(models.StockEntry).filter(
            and_(
                models.StockEntry.site_id == site_id,
                models.StockEntry.material_id == material_id,
                models.StockEntry.entry_date <= as_of_date
            )
        ).all()
        
        # Initialize totals
        total_received = Decimal('0.00')
        total_used = Decimal('0.00')
        total_moved = Decimal('0.00')
        total_return_received = Decimal('0.00')
        total_return_supplier = Decimal('0.00')
        
        # Calculate totals from stock entries
        for entry in stock_entries:
            if entry.entry_type == schemas.StockEntryType.RECEIVED.value:
                total_received += entry.quantity
            elif entry.entry_type == schemas.StockEntryType.USED.value:
                total_used += entry.quantity
            elif entry.entry_type == schemas.StockEntryType.RETURNED_RECEIVED.value:
                total_return_received += entry.quantity
            elif entry.entry_type == schemas.StockEntryType.RETURNED_SUPPLIER.value:
                total_return_supplier += entry.quantity
        
        # Get previous day's closing balance
        previous_day = as_of_date - timedelta(days=1)
        previous_report = crud.crud_daily_report.get_latest_report(
            db, site_id, material_id
        )
        
        previous_balance = Decimal('0.00')
        if previous_report and previous_report.report_date.date() == previous_day.date():
            previous_balance = previous_report.closing_stock
        
        # Calculate current balance using the formula
        # B = PB + R - U - M + rr - rs
        # Note: Moved quantity is handled separately if needed
        current_balance = (
            previous_balance +
            total_received -
            total_used -
            total_moved +
            total_return_received -
            total_return_supplier
        )
        
        # Calculate TR (Total Received of the day)
        # TR = R_N + R_N + R_N - M_N - M_N - M_N + rr_N + rr_N + rr_N
        # For simplicity, we calculate daily received
        today_start = datetime.combine(as_of_date.date(), datetime.min.time())
        today_end = datetime.combine(as_of_date.date(), datetime.max.time())
        
        today_entries = db.query(models.StockEntry).filter(
            and_(
                models.StockEntry.site_id == site_id,
                models.StockEntry.material_id == material_id,
                models.StockEntry.entry_date >= today_start,
                models.StockEntry.entry_date <= today_end
            )
        ).all()
        
        today_received = Decimal('0.00')
        today_moved = Decimal('0.00')
        today_return_received = Decimal('0.00')
        
        for entry in today_entries:
            if entry.entry_type == schemas.StockEntryType.RECEIVED.value:
                today_received += entry.quantity
            elif entry.entry_type == schemas.StockEntryType.USED.value:  # Assuming USED includes moved
                today_moved += entry.quantity
            elif entry.entry_type == schemas.StockEntryType.RETURNED_RECEIVED.value:
                today_return_received += entry.quantity
        
        total_received_today = today_received - today_moved + today_return_received
        
        result = {
            "material_id": material_id,
            "site_id": site_id,
            "as_of_date": as_of_date,
            "opening_balance": previous_balance,
            "total_received": total_received,
            "total_used": total_used,
            "total_moved": total_moved,
            "total_return_received": total_return_received,
            "total_return_supplier": total_return_supplier,
            "current_balance": current_balance,
            "total_received_today": total_received_today,
            "has_negative_balance": current_balance < Decimal('0.00')
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
            # Closing = Opening + Received - Used + Return Received - Return Supplier
            closing_stock = (
                opening_stock +
                daily_received -
                daily_used +
                daily_return_received -
                daily_return_supplier
            )
            
            # Calculate TR (Total Received of the day)
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
        site_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get stock summary for all materials at a site
        """
        logger.debug(f"Getting stock summary for site {site_id}")
        
        summary = []
        
        # Get all materials with activity at this site
        materials_query = db.query(models.Material).join(models.StockEntry).filter(
            models.StockEntry.site_id == site_id
        ).distinct()
        
        materials = materials_query.all()
        
        for material in materials:
            balance = StockCalculator.calculate_balance(db, site_id, material.id)
            
            # ADDED: Find the absolute most recent transaction date for this material
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
                "last_updated": latest_entry_date  # <--- Now sent to Angular!
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
        """
        Validate if a stock entry is allowed (prevent negative stock if needed)
        Note: According to requirements, negative balance is allowed
        """
        logger.debug(f"Validating stock entry: site={site_id}, material={material_id}, type={entry_type}, qty={quantity}")
        
        # Always allow if negative balance is permitted
        # If negative balance was not allowed, we would check here
        
        if entry_type == schemas.StockEntryType.USED.value:
            current_balance = StockCalculator.calculate_balance(
                db, site_id, material_id
            )["current_balance"]
            
            if current_balance < quantity:
                logger.warning(f"Insufficient stock for usage. Balance: {current_balance}, Requested: {quantity}")
                # Still allow as per requirements (negative balance allowed)
        
        return True

# CLI functions for stock operations
def cli_calculate_stock(db: Session, site_id: int, material_id: int):
    """CLI function to calculate and display stock balance"""
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
    print(f"  🔄 Return Received: {result['total_return_received']}")
    print(f"  ↩️  Return to Supplier: {result['total_return_supplier']}")
    print(f"  📊 Current Balance: {result['current_balance']}")
    print(f"  📥 Today's Total Received: {result['total_received_today']}")
    
    if result['has_negative_balance']:
        print("  ⚠️  WARNING: Negative balance detected!")
    
    return result

def cli_generate_daily_report(db: Session, site_id: int, report_date: date):
    """CLI function to generate daily report"""
    print(f"📋 Generating daily report for site {site_id} on {report_date}")
    
    calculator = StockCalculator()
    reports = calculator.generate_daily_report(db, site_id, report_date)
    
    print(f"✅ Generated {len(reports)} daily reports")
    
    for report in reports[:5]:  # Show first 5
        material = db.query(models.Material).filter(models.Material.id == report.material_id).first()
        material_name = material.name if material else f"Material {report.material_id}"
        
        print(f"  📦 {material_name}:")
        print(f"    Opening: {report.opening_stock}")
        print(f"    Received: {report.received}")
        print(f"    Used: {report.used}")
        print(f"    Closing: {report.closing_stock}")
    
    if len(reports) > 5:
        print(f"  ... and {len(reports) - 5} more materials")
    
    return reports
