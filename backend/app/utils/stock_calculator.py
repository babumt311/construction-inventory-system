"""
Stock calculation utilities - Enterprise FIFO Allocation Engine (Crash-Proof)
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
        if quantity <= 0: return False
        if entry_type in ['used', 'returned_supplier']:
            balance = StockCalculator.calculate_balance(db, site_id, material_id)
            if balance['current_balance'] < quantity: return False
        return True
    
    @staticmethod
    def calculate_balance(db: Session, site_id: int, material_id: int, as_of_date: Optional[datetime] = None) -> Dict[str, Any]:
        if not as_of_date:
            as_of_date = datetime.now()
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

        start_dt = datetime.combine(effective_start, time(0, 0, 0))
        end_dt = datetime.combine(effective_end, time(23, 58, 59))

        for material in materials:
            entries = db.query(models.StockEntry).filter(
                models.StockEntry.site_id == site_id,
                models.StockEntry.material_id == material.id,
                models.StockEntry.entry_date <= end_dt
            ).order_by(models.StockEntry.entry_date.asc(), models.StockEntry.id.asc()).all()

            if not entries:
                continue

            lots = [] 
            
            for e in entries:
                safe_date = e.entry_date.replace(tzinfo=None) if getattr(e.entry_date, 'tzinfo', None) else e.entry_date
                
                in_period = (start_dt <= safe_date <= end_dt)
                before_period = (safe_date < start_dt)
                
                if e.entry_type in ['received', 'returned_received']:
                    unit_cost = (e.total_cost / e.quantity) if e.quantity and e.total_cost else Decimal('0.0')
                    lots.append({
                        "supplier_name": e.supplier_name or '-',
                        "invoice_no": e.invoice_no or '-',
                        "invoice_date": e.invoice_date,
                        "unit_cost": unit_cost,
                        "current_balance": e.quantity,
                        "opening_balance": e.quantity if before_period else Decimal('0.0'),
                        "total_received": e.quantity if (in_period and e.entry_type == 'received') else Decimal('0.0'),
                        "received_value": e.total_cost if (in_period and e.entry_type == 'received') else Decimal('0.0'),
                        "total_used": Decimal('0.0'),
                        "used_value": Decimal('0.0'),
                        "total_transfer_out": Decimal('0.0'),
                        "total_transfer_in": e.quantity if (in_period and e.entry_type == 'returned_received') else Decimal('0.0'),
                        "total_returned_supplier": Decimal('0.0'),
                        "last_updated": safe_date
                    })
                    
                elif e.entry_type in ['used', 'returned_supplier']:
                    qty_to_consume = e.quantity
                    
                    for lot in lots:
                        if qty_to_consume <= Decimal('0.0'):
                            break
                        if lot["current_balance"] > Decimal('0.0'):
                            deduct = min(lot["current_balance"], qty_to_consume)
                            lot["current_balance"] -= deduct
                            qty_to_consume -= deduct
                            
                            if before_period:
                                lot["opening_balance"] -= deduct
                                
                            if in_period:
                                if e.entry_type == 'used':
                                    if e.remarks and 'Transfer OUT' in e.remarks:
                                        lot["total_transfer_out"] += deduct
                                    else:
                                        lot["total_used"] += deduct
                                        lot["used_value"] += deduct * lot["unit_cost"]
                                elif e.entry_type == 'returned_supplier':
                                    lot["total_returned_supplier"] += deduct
                            
                            lot["last_updated"] = safe_date

                    if qty_to_consume > Decimal('0.0'):
                        if not lots:
                            lots.append({
                                "supplier_name": '-', "invoice_no": '-', "invoice_date": None, "unit_cost": Decimal('0.0'),
                                "current_balance": Decimal('0.0'), "opening_balance": Decimal('0.0'), "total_received": Decimal('0.0'),
                                "received_value": Decimal('0.0'), "total_used": Decimal('0.0'), "used_value": Decimal('0.0'),
                                "total_transfer_out": Decimal('0.0'), "total_transfer_in": Decimal('0.0'), "total_returned_supplier": Decimal('0.0'),
                                "last_updated": safe_date
                            })
                        last_lot = lots[-1]
                        last_lot["current_balance"] -= qty_to_consume
                        if before_period:
                            last_lot["opening_balance"] -= qty_to_consume
                        if in_period:
                            if e.entry_type == 'used':
                                if e.remarks and 'Transfer OUT' in e.remarks:
                                    last_lot["total_transfer_out"] += qty_to_consume
                                else:
                                    last_lot["total_used"] += qty_to_consume
                                    last_lot["used_value"] += qty_to_consume * last_lot["unit_cost"]
                            elif e.entry_type == 'returned_supplier':
                                last_lot["total_returned_supplier"] += qty_to_consume
                        last_lot["last_updated"] = safe_date

            grouped_lots = {}
            for lot in lots:
                key = (str(lot["supplier_name"]), str(lot["invoice_no"]))
                if key not in grouped_lots:
                    grouped_lots[key] = lot.copy()
                else:
                    g = grouped_lots[key]
                    g["current_balance"] += lot["current_balance"]
                    g["opening_balance"] += lot["opening_balance"]
                    g["total_received"] += lot["total_received"]
                    g["received_value"] += lot["received_value"]
                    g["total_used"] += lot["total_used"]
                    g["used_value"] += lot["used_value"]
                    g["total_transfer_out"] += lot["total_transfer_out"]
                    g["total_transfer_in"] += lot["total_transfer_in"]
                    g["total_returned_supplier"] += lot["total_returned_supplier"]
                    if lot["last_updated"] > g["last_updated"]: g["last_updated"] = lot["last_updated"]
                    if not g["invoice_date"] and lot["invoice_date"]: g["invoice_date"] = lot["invoice_date"]

            for key, g in grouped_lots.items():
                has_activity = (g["total_received"] > 0 or g["total_used"] > 0 or g["total_transfer_out"] > 0 or g["total_transfer_in"] > 0 or g["total_returned_supplier"] > 0)
                
                # --- NEW STRICT MOVEMENT LOGIC ---
                # If checking a specific date range in the UI, hide lots that didn't move at all!
                if has_date_filter and not has_activity and not is_daily_report:
                    continue
                    
                # If checking "All Time", hide ghost entries that have 0 balance and 0 activity
                if not has_date_filter and g["opening_balance"] == 0 and not has_activity and g["current_balance"] == 0:
                    continue
                # ---------------------------------
                
                summary.append({
                    "material_id": material.id,
                    "material_name": material.name,
                    "category": material.category.name if material.category else "N/A",
                    "unit": material.unit or "N/A",
                    "current_balance": g["current_balance"],
                    "opening_balance": g["opening_balance"],
                    "total_received": g["total_received"],
                    "received_value": g["received_value"],
                    "total_used": g["total_used"],
                    "used_value": g["used_value"],
                    "total_returned_supplier": g["total_returned_supplier"],
                    "total_transfer_in": g["total_transfer_in"],
                    "total_transfer_out": g["total_transfer_out"],
                    "has_negative_balance": g["current_balance"] < 0,
                    "supplier_name": g["supplier_name"],
                    "invoice_no": g["invoice_no"],
                    "invoice_date": g["invoice_date"],
                    "last_updated": g["last_updated"] if has_activity else end_dt
                })

        if supplier_name:
            search_str = supplier_name.lower()
            summary = [s for s in summary if search_str in str(s['supplier_name']).lower()]
            
        if entry_type:
            if entry_type == 'received': summary = [s for s in summary if s['total_received'] > 0]
            elif entry_type == 'used': summary = [s for s in summary if s['total_used'] > 0]
            elif entry_type == 'transfer': summary = [s for s in summary if s['total_transfer_out'] > 0 or s['total_transfer_in'] > 0]
            elif entry_type == 'returned_supplier': summary = [s for s in summary if s['total_returned_supplier'] > 0]

        return summary

    @staticmethod
    def generate_daily_report(db: Session, site_id: int, report_date: date) -> List[models.DailyStockReport]:
        # is_daily_report=True ensures the automated cron job STILL saves items even if they had 0 movement that day
        summary = StockCalculator.get_site_stock_summary(db, site_id, report_date, report_date, is_daily_report=True)
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

# --- CLI Helpers ---
def cli_calculate_stock(db: Session, site_id: int, material_id: int):
    calculator = StockCalculator()
    return calculator.calculate_balance(db, site_id, material_id)

def cli_generate_daily_report(db: Session, site_id: int, report_date: date):
    calculator = StockCalculator()
    return calculator.generate_daily_report(db, site_id, report_date)
