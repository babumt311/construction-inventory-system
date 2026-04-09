"""
Stock calculation utilities - Immutable Ledger Edition
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import logging
from app import models, schemas

logger = logging.getLogger(__name__)

class StockCalculator:

    @staticmethod
    def validate_stock_entry(db: Session, site_id: int, material_id: int, entry_type: str, quantity: Decimal) -> bool:
        """Validate if a stock entry is allowed (e.g., prevents negative stock)"""
        if quantity <= 0:
            return False
            
        # If removing stock, check if we have enough
        if entry_type in ['used', 'returned_supplier']:
            balance = StockCalculator.calculate_balance(db, site_id, material_id)
            if balance['current_balance'] < quantity:
                return False
                
        return True
    
    @staticmethod
    def calculate_balance(db: Session, site_id: int, material_id: int, as_of_date: Optional[datetime] = None) -> Dict[str, Any]:
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
            if entry.entry_type in ['received', 'returned_received']:
                all_time_received += entry.quantity
            elif entry.entry_type in ['used', 'returned_supplier']:
                all_time_used += entry.quantity
                
        current_balance = all_time_received - all_time_used
        
        yesterday_end = datetime.combine((as_of_date - timedelta(days=1)).date(), datetime.max.time())
        opening_balance = Decimal('0.00')
        
        for entry in all_entries:
            safe_date = entry.entry_date.replace(tzinfo=None) if getattr(entry.entry_date, 'tzinfo', None) else entry.entry_date
            if safe_date <= yesterday_end:
                if entry.entry_type in ['received', 'returned_received']:
                    opening_balance += entry.quantity
                elif entry.entry_type in ['used', 'returned_supplier']:
                    opening_balance -= entry.quantity

        today_start = datetime.combine(as_of_date.date(), datetime.min.time())
        today_end = datetime.combine(as_of_date.date(), datetime.max.time())
        
        today_received = Decimal('0.00')
        today_used = Decimal('0.00')
        today_received_value = Decimal('0.00') 
        today_used_value = Decimal('0.00')     
        today_return_supplier = Decimal('0.00')
        today_transfer_in = Decimal('0.00')
        today_transfer_out = Decimal('0.00')
        
        for entry in all_entries:
            safe_date = entry.entry_date.replace(tzinfo=None) if getattr(entry.entry_date, 'tzinfo', None) else entry.entry_date
            
            if today_start <= safe_date <= today_end:
                entry_cost = entry.total_cost or Decimal('0.00') 
                
                if entry.entry_type == 'received':
                    today_received += entry.quantity
                    today_received_value += entry_cost
                elif entry.entry_type == 'used':
                    if entry.remarks and 'Transfer OUT' in entry.remarks:
                        today_transfer_out += entry.quantity
                    else:
                        today_used += entry.quantity
                        today_used_value += entry_cost
                elif entry.entry_type == 'returned_received':
                    today_transfer_in += entry.quantity 
                elif entry.entry_type == 'returned_supplier':
                    today_return_supplier += entry.quantity
                    
        return {
            "material_id": material_id,
            "site_id": site_id,
            "as_of_date": as_of_date,
            "opening_balance": opening_balance,
            "total_received": today_received, 
            "received_value": today_received_value, 
            "total_used": today_used, 
            "used_value": today_used_value,         
            "total_returned_supplier": today_return_supplier,
            "total_transfer_in": today_transfer_in,
            "total_transfer_out": today_transfer_out,
            "current_balance": current_balance,
            "has_negative_balance": current_balance < Decimal('0.00')
        }
    
    @staticmethod
    def get_latest_supplier_info(db: Session, site_id: int, material_id: int, as_of: datetime = None):
        """Detective function: Looks back in time to find the original supplier/invoice"""
        query = db.query(models.StockEntry).filter(
            models.StockEntry.material_id == material_id,
            models.StockEntry.supplier_name.isnot(None),
            models.StockEntry.supplier_name != ''
        )
        if as_of:
            query = query.filter(models.StockEntry.entry_date <= as_of)
            
        # Try finding it for this specific site first
        site_query = query.filter(models.StockEntry.site_id == site_id).order_by(models.StockEntry.entry_date.desc()).first()
        if site_query:
            return site_query
            
        # Fallback to any site (if it was transferred in from somewhere else)
        return query.order_by(models.StockEntry.entry_date.desc()).first()

    @staticmethod
    def get_site_stock_summary(db: Session, site_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None, supplier_name: Optional[str] = None, entry_type: Optional[str] = None) -> List[Dict[str, Any]]:
        summary = []
        materials = db.query(models.Material).join(models.StockEntry).filter(
            models.StockEntry.site_id == site_id
        ).distinct().all()

        has_date_filter = bool(start_date or end_date)
        effective_start = start_date if start_date else date.min
        effective_end = end_date if end_date else date.today()
        
        start_dt = datetime.combine(effective_start, datetime.min.time())
        end_dt = datetime.combine(effective_end, datetime.max.time())

        for material in materials:
            # 1. STRICT START DATE: Find exact balance the millisecond before start date
            if has_date_filter and start_date:
                opening_calc = StockCalculator.calculate_balance(db, site_id, material.id, start_dt - timedelta(microseconds=1))
                opening_bal = opening_calc["current_balance"]
                prev_tot_rec_qty = opening_calc.get("total_received", Decimal('0.0'))
                prev_tot_rec_val = opening_calc.get("received_value", Decimal('0.0'))
            else:
                opening_bal = Decimal('0.0')
                prev_tot_rec_qty = Decimal('0.0')
                prev_tot_rec_val = Decimal('0.0')

            entries = db.query(models.StockEntry).filter(
                models.StockEntry.site_id == site_id,
                models.StockEntry.material_id == material.id,
                models.StockEntry.entry_date >= start_dt,
                models.StockEntry.entry_date <= end_dt
            ).order_by(models.StockEntry.entry_date.asc()).all()

            # 2. STRICT ISOLATION: If a date range is active, skip materials with 0 transactions in this window
            if has_date_filter and len(entries) == 0:
                continue
            
            # If no date filter, skip only if absolutely no history (fallback)
            if not has_date_filter and len(entries) == 0 and opening_bal == 0:
                continue

            period_received = Decimal('0.0')
            period_received_value = Decimal('0.0')
            period_used = Decimal('0.0')
            period_returned_supplier = Decimal('0.0')
            period_transfer_in = Decimal('0.0')
            period_transfer_out = Decimal('0.0')

            latest_in_range = None
            latest_sup_in_range = "-"
            latest_inv_in_range = "-"
            latest_inv_date_in_range = None
            
            # 3. ONLY process math for transactions that occurred strictly within the dates
            for e in entries:
                latest_in_range = e.entry_date
                entry_cost = e.total_cost or Decimal('0.0')
                
                if e.supplier_name and str(e.supplier_name).strip() != "" and str(e.supplier_name).strip() != "-":
                    latest_sup_in_range = e.supplier_name
                    latest_inv_in_range = e.invoice_no
                    latest_inv_date_in_range = e.invoice_date

                if e.entry_type == 'received':
                    period_received += e.quantity
                    period_received_value += entry_cost
                elif e.entry_type == 'used':
                    if e.remarks and 'Transfer OUT' in e.remarks:
                        period_transfer_out += e.quantity
                    else:
                        period_used += e.quantity
                elif e.entry_type == 'returned_received':
                    period_transfer_in += e.quantity
                elif e.entry_type == 'returned_supplier':
                    period_returned_supplier += e.quantity

            closing_bal = opening_bal + period_received + period_transfer_in - period_used - period_transfer_out - period_returned_supplier

            tot_rec_qty = prev_tot_rec_qty + period_received
            tot_rec_val = prev_tot_rec_val + period_received_value
            avg_cost = tot_rec_val / tot_rec_qty if tot_rec_qty > 0 else Decimal('0.0')
            dynamic_used_value = period_used * avg_cost

            # Origin inheritance: If no supplier found IN the range, look backward historically
            if latest_sup_in_range == "-":
                sup_info = StockCalculator.get_latest_supplier_info(db, site_id, material.id, end_dt)
                if sup_info:
                    latest_sup_in_range = sup_info.supplier_name
                    latest_inv_in_range = sup_info.invoice_no
                    latest_inv_date_in_range = sup_info.invoice_date

            summary.append({
                "material_id": material.id,
                "material_name": material.name,
                "category": material.category.name if material.category else "N/A",
                "unit": material.unit or "N/A",
                "current_balance": closing_bal,
                "opening_balance": opening_bal,
                "total_received": period_received,
                "received_value": period_received_value,
                "total_used": period_used,
                "used_value": dynamic_used_value,
                "total_returned_supplier": period_returned_supplier,
                "total_transfer_in": period_transfer_in,
                "total_transfer_out": period_transfer_out,
                "has_negative_balance": closing_bal < 0,
                "supplier_name": latest_sup_in_range,
                "invoice_no": latest_inv_in_range,
                "invoice_date": latest_inv_date_in_range,
                "last_updated": latest_in_range if latest_in_range else (end_dt if start_date else None)
            })

        # 4. Post-Process Backend Filters
        if supplier_name:
            search_str = supplier_name.lower()
            summary = [s for s in summary if s['supplier_name'] and search_str in s['supplier_name'].lower()]
            
        if entry_type:
            if entry_type == 'received':
                summary = [s for s in summary if s['total_received'] > 0]
            elif entry_type == 'used':
                summary = [s for s in summary if s['total_used'] > 0]
            elif entry_type == 'transfer':
                summary = [s for s in summary if s['total_transfer_out'] > 0 or s['total_transfer_in'] > 0]
            elif entry_type == 'returned_supplier':
                summary = [s for s in summary if s['total_returned_supplier'] > 0]

        return summary

    @staticmethod
    def generate_daily_report(db: Session, site_id: int, report_date: date) -> List[models.DailyStockReport]:
        summary = StockCalculator.get_site_stock_summary(db, site_id, report_date, report_date)
        reports_generated = []
        
        report_datetime = datetime.combine(report_date, datetime.min.time())
        
        for item in summary:
            existing_report = db.query(models.DailyStockReport).filter(
                models.DailyStockReport.site_id == site_id,
                models.DailyStockReport.material_id == item["material_id"],
                models.DailyStockReport.report_date == report_datetime
            ).first()
            
            if existing_report:
                existing_report.opening_stock = item["opening_balance"]
                existing_report.received = item["total_received"]
                existing_report.used = item["total_used"]
                existing_report.returned_received = item["total_transfer_in"]
                existing_report.returned_supplier = item["total_returned_supplier"]
                existing_report.closing_stock = item["current_balance"]
                existing_report.received_value = item["received_value"]
                existing_report.used_value = item["used_value"]
                reports_generated.append(existing_report)
            else:
                new_report = models.DailyStockReport(
                    site_id=site_id,
                    material_id=item["material_id"],
                    report_date=report_datetime,
                    opening_stock=item["opening_balance"],
                    received=item["total_received"],
                    used=item["total_used"],
                    returned_received=item["total_transfer_in"],
                    returned_supplier=item["total_returned_supplier"],
                    closing_stock=item["current_balance"],
                    total_received=item["total_received"],
                    received_value=item["received_value"],
                    used_value=item["used_value"]
                )
                db.add(new_report)
                reports_generated.append(new_report)
                
        db.commit()
        return reports_generated

def cli_calculate_stock(db: Session, site_id: int, material_id: int):
    calculator = StockCalculator()
    return calculator.calculate_balance(db, site_id, material_id)

def cli_generate_daily_report(db: Session, site_id: int, report_date: date):
    calculator = StockCalculator()
    return calculator.generate_daily_report(db, site_id, report_date)
