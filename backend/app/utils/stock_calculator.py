"""
Stock calculation utilities - Enterprise Lot Tracking Edition (Strict Timeline)
"""
from datetime import datetime, date, timedelta, time
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
        if quantity <= 0:
            return False
            
        if entry_type in ['used', 'returned_supplier']:
            balance = StockCalculator.calculate_balance(db, site_id, material_id)
            if balance['current_balance'] < quantity:
                return False
                
        return True
    
    @staticmethod
    def calculate_balance(db: Session, site_id: int, material_id: int, as_of_date: Optional[datetime] = None, supplier_name: Optional[str] = None, invoice_no: Optional[str] = None) -> Dict[str, Any]:
        if not as_of_date:
            as_of_date = datetime.now()
        as_of_date = as_of_date.replace(tzinfo=None) if getattr(as_of_date, 'tzinfo', None) else as_of_date
            
        query = db.query(models.StockEntry).filter(
            models.StockEntry.site_id == site_id,
            models.StockEntry.material_id == material_id,
            models.StockEntry.entry_date <= as_of_date
        )
        
        # BATCH ISOLATION
        if supplier_name is not None:
            query = query.filter(func.coalesce(models.StockEntry.supplier_name, '-') == supplier_name)
        if invoice_no is not None:
            query = query.filter(func.coalesce(models.StockEntry.invoice_no, '-') == invoice_no)
            
        all_entries = query.all()
        
        all_time_received = Decimal('0.00')
        all_time_received_value = Decimal('0.00') # Keep track of exact historic cost
        all_time_used = Decimal('0.00')
        
        for entry in all_entries:
            if entry.entry_type in ['received', 'returned_received']:
                all_time_received += entry.quantity
                all_time_received_value += (entry.total_cost or Decimal('0.00'))
            elif entry.entry_type in ['used', 'returned_supplier']:
                all_time_used += entry.quantity
                
        current_balance = all_time_received - all_time_used
        
        # STRICT TIMELINE: Yesterday ends exactly at 11:58:59 PM
        yesterday_end = datetime.combine((as_of_date - timedelta(days=1)).date(), time(23, 58, 59))
        opening_balance = Decimal('0.00')
        
        for entry in all_entries:
            safe_date = entry.entry_date.replace(tzinfo=None) if getattr(entry.entry_date, 'tzinfo', None) else entry.entry_date
            if safe_date <= yesterday_end:
                if entry.entry_type in ['received', 'returned_received']:
                    opening_balance += entry.quantity
                elif entry.entry_type in ['used', 'returned_supplier']:
                    opening_balance -= entry.quantity

        # STRICT TIMELINE: Today boundaries (Ends at 11:58:59 PM)
        today_start = datetime.combine(as_of_date.date(), time(0, 0, 0))
        today_end = datetime.combine(as_of_date.date(), time(23, 58, 59))
        
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
            "has_negative_balance": current_balance < Decimal('0.00'),
            "all_time_received": all_time_received,
            "all_time_received_value": all_time_received_value
        }
    
    @staticmethod
    def get_latest_supplier_info(db: Session, site_id: int, material_id: int, as_of: datetime = None):
        query = db.query(models.StockEntry).filter(
            models.StockEntry.material_id == material_id,
            models.StockEntry.supplier_name.isnot(None),
            models.StockEntry.supplier_name != ''
        )
        if as_of:
            query = query.filter(models.StockEntry.entry_date <= as_of)
            
        site_query = query.filter(models.StockEntry.site_id == site_id).order_by(models.StockEntry.entry_date.desc()).first()
        if site_query: return site_query
        return query.order_by(models.StockEntry.entry_date.desc()).first()

    @staticmethod
    def get_site_stock_summary(db: Session, site_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None, supplier_name: Optional[str] = None, entry_type: Optional[str] = None) -> List[Dict[str, Any]]:
        summary = []
        
        lots = db.query(
            models.StockEntry.material_id,
            func.coalesce(models.StockEntry.supplier_name, '-').label('supplier_name'),
            func.coalesce(models.StockEntry.invoice_no, '-').label('invoice_no')
        ).filter(models.StockEntry.site_id == site_id).distinct().all()

        has_date_filter = bool(start_date or end_date)
        effective_start = start_date if start_date else date.min
        effective_end = end_date if end_date else date.today()
        
        # STRICT TIMELINE: Lock borders strictly inside 00:00:00 and 23:58:59
        start_dt = datetime.combine(effective_start, time(0, 0, 0))
        end_dt = datetime.combine(effective_end, time(23, 58, 59))

        for lot in lots:
            mat_id = lot.material_id
            sup_name = lot.supplier_name
            inv_no = lot.invoice_no
            
            material = db.query(models.Material).filter(models.Material.id == mat_id).first()
            if not material:
                continue

            if has_date_filter and start_date:
                # Get balance 1 second before the period begins
                opening_calc = StockCalculator.calculate_balance(db, site_id, mat_id, start_dt - timedelta(seconds=1), sup_name, inv_no)
                opening_bal = opening_calc["current_balance"]
                # Use absolute historical values so average cost isn't wiped out by the date filter
                prev_tot_rec_qty = opening_calc.get("all_time_received", Decimal('0.0'))
                prev_tot_rec_val = opening_calc.get("all_time_received_value", Decimal('0.0'))
            else:
                opening_bal = Decimal('0.0')
                prev_tot_rec_qty = Decimal('0.0')
                prev_tot_rec_val = Decimal('0.0')

            entries = db.query(models.StockEntry).filter(
                models.StockEntry.site_id == site_id,
                models.StockEntry.material_id == mat_id,
                models.StockEntry.entry_date >= start_dt,
                models.StockEntry.entry_date <= end_dt,
                func.coalesce(models.StockEntry.supplier_name, '-') == sup_name,
                func.coalesce(models.StockEntry.invoice_no, '-') == inv_no
            ).order_by(models.StockEntry.entry_date.asc()).all()

            # Skip if absolutely zero activity and zero opening balance
            if len(entries) == 0 and opening_bal == 0:
                continue

            period_received = Decimal('0.0')
            period_received_value = Decimal('0.0')
            period_used = Decimal('0.0')
            period_returned_supplier = Decimal('0.0')
            period_transfer_in = Decimal('0.0')
            period_transfer_out = Decimal('0.0')

            latest_in_range = None
            
            for e in entries:
                latest_in_range = e.entry_date
                entry_cost = e.total_cost or Decimal('0.0')
                
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

            latest_inv_date = None
            if len(entries) > 0:
                for e in entries:
                    if e.invoice_date: latest_inv_date = e.invoice_date
            else:
                last_entry = db.query(models.StockEntry).filter(
                    models.StockEntry.site_id == site_id,
                    models.StockEntry.material_id == mat_id,
                    func.coalesce(models.StockEntry.supplier_name, '-') == sup_name,
                    func.coalesce(models.StockEntry.invoice_no, '-') == inv_no
                ).order_by(models.StockEntry.entry_date.desc()).first()
                if last_entry:
                    latest_inv_date = last_entry.invoice_date

            # Clean Display Date: Show the exact date it was updated, or default to the End Date filter
            if latest_in_range:
                final_updated = latest_in_range
            elif has_date_filter:
                final_updated = end_dt
            else:
                last_historic_entry = db.query(models.StockEntry).filter(
                    models.StockEntry.site_id == site_id,
                    models.StockEntry.material_id == mat_id,
                    func.coalesce(models.StockEntry.supplier_name, '-') == sup_name,
                    func.coalesce(models.StockEntry.invoice_no, '-') == inv_no
                ).order_by(models.StockEntry.entry_date.desc()).first()
                final_updated = last_historic_entry.entry_date if last_historic_entry else None

            summary.append({
                "material_id": mat_id,
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
                "supplier_name": sup_name,
                "invoice_no": inv_no,
                "invoice_date": latest_inv_date,
                "last_updated": final_updated
            })

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
        
        aggregated = {}
        for item in summary:
            mat_id = item["material_id"]
            if mat_id not in aggregated:
                aggregated[mat_id] = item.copy()
            else:
                aggregated[mat_id]["opening_balance"] += item["opening_balance"]
                aggregated[mat_id]["total_received"] += item["total_received"]
                aggregated[mat_id]["received_value"] += item["received_value"]
                aggregated[mat_id]["total_used"] += item["total_used"]
                aggregated[mat_id]["used_value"] += item["used_value"]
                aggregated[mat_id]["total_returned_supplier"] += item["total_returned_supplier"]
                aggregated[mat_id]["total_transfer_in"] += item["total_transfer_in"]
                aggregated[mat_id]["total_transfer_out"] += item["total_transfer_out"]
                aggregated[mat_id]["current_balance"] += item["current_balance"]

        for mat_id, item in aggregated.items():
            existing_report = db.query(models.DailyStockReport).filter(
                models.DailyStockReport.site_id == site_id,
                models.DailyStockReport.material_id == mat_id,
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
