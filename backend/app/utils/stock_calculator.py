"""
Stock calculation utilities - Enterprise Daily Consolidated Ledger
"""
from datetime import datetime, date, timedelta, time
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging
from app import models

logger = logging.getLogger(__name__)

class StockCalculator:

    @staticmethod
    def validate_stock_entry(db: Session, site_id: int, material_id: int, entry_type: str, quantity: Decimal) -> bool:
        if quantity <= 0: return False
        if entry_type in ['used', 'returned_supplier']:
            balance = StockCalculator.calculate_balance(db, site_id, material_id)
            if balance['current_balance'] < quantity: return False
        return True
    
    @staticmethod
    def calculate_balance(db: Session, site_id: int, material_id: int, as_of_date: Optional[datetime] = None) -> Dict[str, Any]:
        if not as_of_date: as_of_date = datetime.now()
        as_of_date = as_of_date.replace(tzinfo=None) if getattr(as_of_date, 'tzinfo', None) else as_of_date
            
        all_entries = db.query(models.StockEntry).filter(
            models.StockEntry.site_id == site_id,
            models.StockEntry.material_id == material_id,
            models.StockEntry.entry_date <= as_of_date
        ).all()
        
        all_time_received = sum((e.quantity for e in all_entries if e.entry_type in ['received', 'returned_received']), Decimal('0.0'))
        all_time_used = sum((e.quantity for e in all_entries if e.entry_type in ['used', 'returned_supplier']), Decimal('0.0'))
        current_balance = all_time_received - all_time_used
        
        return {
            "current_balance": current_balance,
            "total_received": all_time_received, 
            "total_used": all_time_used, 
            "has_negative_balance": current_balance < Decimal('0.0')
        }

    @staticmethod
    def get_site_stock_summary(db: Session, site_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None, supplier_name: Optional[str] = None, entry_type: Optional[str] = None, is_daily_report: bool = False) -> List[Dict[str, Any]]:
        summary = []
        materials = db.query(models.Material).join(models.StockEntry).filter(models.StockEntry.site_id == site_id).distinct().all()

        has_date_filter = bool(start_date or end_date)
        effective_start = start_date if start_date else date(2000, 1, 1)
        effective_end = end_date if end_date else (date.today() + timedelta(days=3650))

        for material in materials:
            entries = db.query(models.StockEntry).filter(
                models.StockEntry.site_id == site_id,
                models.StockEntry.material_id == material.id,
                func.date(models.StockEntry.entry_date) <= effective_end
            ).order_by(models.StockEntry.entry_date.asc(), models.StockEntry.id.asc()).all()

            if not entries and not is_daily_report: continue

            global_running_balance = Decimal('0.0')
            entries_by_date = {}

            # Group entries by exact day
            for e in entries:
                safe_date = e.entry_date.replace(tzinfo=None) if getattr(e.entry_date, 'tzinfo', None) else e.entry_date
                d = safe_date.date()
                if d not in entries_by_date: entries_by_date[d] = []
                entries_by_date[d].append(e)

            sorted_dates = sorted(entries_by_date.keys())
            if is_daily_report and effective_end not in entries_by_date:
                sorted_dates.append(effective_end)
                entries_by_date[effective_end] = []

            # Process chronologically day-by-day
            for current_date in sorted_dates:
                opening_balance_today = global_running_balance
                daily_receipts = []
                
                # Daily accumulator
                act = {
                    "recv": Decimal('0.0'), "recv_val": Decimal('0.0'), 
                    "used": Decimal('0.0'), "used_val": Decimal('0.0'), 
                    "t_out": Decimal('0.0'), "t_in": Decimal('0.0'), 
                    "ret": Decimal('0.0')
                }

                for e in entries_by_date[current_date]:
                    qty = e.quantity
                    cost = e.total_cost or Decimal('0.0')
                    
                    if e.entry_type in ['received', 'returned_received']:
                        global_running_balance += qty
                        if e.entry_type == 'received':
                            act["recv"] += qty
                            act["recv_val"] += cost
                            # Store granular receipt for "Received" filter mode
                            daily_receipts.append({
                                "sup": e.supplier_name or '-', "inv": e.invoice_no or '-', "inv_date": e.invoice_date,
                                "qty": qty, "val": cost, "run_bal": global_running_balance, "entry_dt": e.entry_date
                            })
                        else:
                            act["t_in"] += qty
                            
                    elif e.entry_type in ['used', 'returned_supplier']:
                        global_running_balance -= qty
                        if e.entry_type == 'used':
                            if e.remarks and 'Transfer OUT' in e.remarks: act["t_out"] += qty
                            else: act["used"] += qty; act["used_val"] += cost
                        else:
                            act["ret"] += qty

                closing_balance_today = global_running_balance
                
                # Output rows if within the date filter range
                if effective_start <= current_date <= effective_end:
                    has_movement = sum(act.values()) > 0
                    
                    # MODE 1: Granular Audit Mode (Only triggered if filter is exactly 'received')
                    if entry_type == 'received':
                        for r in daily_receipts:
                            if supplier_name and supplier_name.lower() not in r["sup"].lower(): continue
                            summary.append({
                                "material_id": material.id, "material_name": material.name,
                                "category": material.category.name if material.category else "N/A",
                                "unit": material.unit or "N/A",
                                "current_balance": r["run_bal"], "opening_balance": r["run_bal"] - r["qty"],
                                "total_received": r["qty"], "received_value": r["val"],
                                "total_used": Decimal('0.0'), "used_value": Decimal('0.0'),
                                "total_returned_supplier": Decimal('0.0'), "total_transfer_in": Decimal('0.0'), "total_transfer_out": Decimal('0.0'),
                                "has_negative_balance": r["run_bal"] < 0,
                                "supplier_name": r["sup"], "invoice_no": r["inv"], "invoice_date": r["inv_date"],
                                "last_updated": r["entry_dt"]
                            })
                    
                    # MODE 2: Consolidated Ledger Mode (All Transactions, Used, etc.)
                    else:
                        if has_movement or is_daily_report:
                            summary.append({
                                "material_id": material.id, "material_name": material.name,
                                "category": material.category.name if material.category else "N/A",
                                "unit": material.unit or "N/A",
                                "current_balance": closing_balance_today, "opening_balance": opening_balance_today,
                                "total_received": act["recv"], "received_value": act["recv_val"],
                                "total_used": act["used"], "used_value": act["used_val"],
                                "total_returned_supplier": act["ret"],
                                "total_transfer_in": act["t_in"], "total_transfer_out": act["t_out"],
                                "has_negative_balance": closing_balance_today < 0,
                                "supplier_name": "-", "invoice_no": "-", "invoice_date": None,
                                "last_updated": datetime.combine(current_date, time(23,59,0))
                            })

        # Process post-generation filtering for non-received types
        if entry_type and entry_type != 'received':
            if entry_type == 'used': summary = [s for s in summary if s['total_used'] > 0]
            elif entry_type == 'transfer': summary = [s for s in summary if s['total_transfer_out'] > 0 or s['total_transfer_in'] > 0]
            elif entry_type == 'returned_supplier': summary = [s for s in summary if s['total_returned_supplier'] > 0]

        return summary

    @staticmethod
    def generate_daily_report(db: Session, site_id: int, report_date: date) -> List[models.DailyStockReport]:
        summary = StockCalculator.get_site_stock_summary(db, site_id, report_date, report_date, is_daily_report=True)
        reports_generated = []
        report_datetime = datetime.combine(report_date, datetime.min.time())
        
        for item in summary:
            existing_report = db.query(models.DailyStockReport).filter(
                models.DailyStockReport.site_id == site_id,
                models.DailyStockReport.material_id == item["material_id"],
                models.DailyStockReport.report_date == report_datetime
            ).first()
            if existing_report:
                existing_report.opening_stock = item["opening_balance"]; existing_report.received = item["total_received"]
                existing_report.used = item["total_used"]; existing_report.returned_received = item["total_transfer_in"]
                existing_report.returned_supplier = item["total_returned_supplier"]; existing_report.closing_stock = item["current_balance"]
                existing_report.received_value = item["received_value"]; existing_report.used_value = item["used_value"]
                reports_generated.append(existing_report)
            else:
                new_report = models.DailyStockReport(
                    site_id=site_id, material_id=item["material_id"], report_date=report_datetime,
                    opening_stock=item["opening_balance"], received=item["total_received"], used=item["total_used"],
                    returned_received=item["total_transfer_in"], returned_supplier=item["total_returned_supplier"],
                    closing_stock=item["current_balance"], total_received=item["total_received"],
                    received_value=item["received_value"], used_value=item["used_value"]
                )
                db.add(new_report); reports_generated.append(new_report)
        db.commit()
        return reports_generated

# --- CLI Helpers ---
def cli_calculate_stock(db: Session, site_id: int, material_id: int):
    return StockCalculator().calculate_balance(db, site_id, material_id)

def cli_generate_daily_report(db: Session, site_id: int, report_date: date):
    return StockCalculator().generate_daily_report(db, site_id, report_date)
