"""
Stock calculation utilities - Daily Chronological Ledger
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

            if not entries and not is_daily_report:
                continue

            lots = [] 
            running_balances = {} 

            # 1. Group all historical entries by exactly what day they happened
            entries_by_date = {}
            for e in entries:
                safe_date = e.entry_date.replace(tzinfo=None) if getattr(e.entry_date, 'tzinfo', None) else e.entry_date
                d = safe_date.date()
                if d not in entries_by_date: entries_by_date[d] = []
                entries_by_date[d].append(e)

            sorted_dates = sorted(entries_by_date.keys())
            
            # If cron job calls, ensure the report date is processed to capture sitting inventory
            if is_daily_report and effective_end not in entries_by_date:
                sorted_dates.append(effective_end)
                entries_by_date[effective_end] = []

            # 2. Process Chronologically Day-by-Day
            for current_date in sorted_dates:
                daily_entries = entries_by_date[current_date]
                opening_balances_today = {k: v for k, v in running_balances.items()}
                daily_activity = {}
                
                def get_daily(sup, inv):
                    k = (sup, inv)
                    if k not in daily_activity:
                        daily_activity[k] = {
                            "received": Decimal('0.0'), "received_val": Decimal('0.0'),
                            "used": Decimal('0.0'), "used_val": Decimal('0.0'),
                            "transfer_out": Decimal('0.0'), "transfer_in": Decimal('0.0'),
                            "returned_supplier": Decimal('0.0'), "invoice_date": None
                        }
                    return daily_activity[k]

                # Run FIFO logic strictly for the events that happened on THIS specific day
                for e in daily_entries:
                    if e.entry_type in ['received', 'returned_received']:
                        sup = e.supplier_name or '-'
                        inv = e.invoice_no or '-'
                        inv_date = e.invoice_date
                        qty = e.quantity
                        cost = e.total_cost or Decimal('0.0')
                        u_cost = (cost / qty) if qty else Decimal('0.0')

                        lots.append({
                            "sup": sup, "inv": inv, "inv_date": inv_date,
                            "qty": qty, "u_cost": u_cost
                        })
                        running_balances[(sup, inv)] = running_balances.get((sup, inv), Decimal('0.0')) + qty
                        
                        act = get_daily(sup, inv)
                        act["invoice_date"] = inv_date
                        if e.entry_type == 'received':
                            act["received"] += qty
                            act["received_val"] += cost
                        else:
                            act["transfer_in"] += qty
                            
                    elif e.entry_type in ['used', 'returned_supplier']:
                        qty_to_consume = e.quantity
                        for lot in lots:
                            if qty_to_consume <= Decimal('0.0'): break
                            if lot["qty"] > Decimal('0.0'):
                                deduct = min(lot["qty"], qty_to_consume)
                                lot["qty"] -= deduct
                                qty_to_consume -= deduct
                                
                                sup, inv = lot["sup"], lot["inv"]
                                running_balances[(sup, inv)] -= deduct
                                
                                act = get_daily(sup, inv)
                                act["invoice_date"] = lot["inv_date"]
                                if e.entry_type == 'used':
                                    if e.remarks and 'Transfer OUT' in e.remarks:
                                        act["transfer_out"] += deduct
                                    else:
                                        act["used"] += deduct
                                        act["used_val"] += deduct * lot["u_cost"]
                                else:
                                    act["returned_supplier"] += deduct
                                    
                        if qty_to_consume > Decimal('0.0'):
                            sup, inv = '-', '-'
                            running_balances[(sup, inv)] = running_balances.get((sup, inv), Decimal('0.0')) - qty_to_consume
                            act = get_daily(sup, inv)
                            if e.entry_type == 'used':
                                if e.remarks and 'Transfer OUT' in e.remarks:
                                    act["transfer_out"] += qty_to_consume
                                else:
                                    act["used"] += qty_to_consume
                            else:
                                act["returned_supplier"] += qty_to_consume

                # 3. Create discrete output rows exclusively for this day
                in_range = True
                if has_date_filter:
                    in_range = (effective_start <= current_date <= effective_end)
                    
                if in_range:
                    keys_to_emit = set(daily_activity.keys())
                    if is_daily_report:
                        keys_to_emit.update(running_balances.keys())
                        
                    for k in keys_to_emit:
                        sup, inv = k
                        act = daily_activity.get(k, {
                            "received": Decimal('0.0'), "received_val": Decimal('0.0'),
                            "used": Decimal('0.0'), "used_val": Decimal('0.0'),
                            "transfer_out": Decimal('0.0'), "transfer_in": Decimal('0.0'),
                            "returned_supplier": Decimal('0.0'), "invoice_date": None
                        })
                        
                        opening = opening_balances_today.get(k, Decimal('0.0'))
                        closing = running_balances.get(k, Decimal('0.0'))
                        
                        has_act = any(act[x] > 0 for x in ["received", "used", "transfer_out", "transfer_in", "returned_supplier"])
                        
                        # LEDGER RULE: If the material wasn't touched on this day, DO NOT show it in the table.
                        if not has_act and not is_daily_report:
                            continue
                            
                        if opening == 0 and closing == 0 and not has_act:
                            continue

                        updated_dt = datetime.combine(current_date, time(12,0,0))
                        
                        summary.append({
                            "material_id": material.id,
                            "material_name": material.name,
                            "category": material.category.name if material.category else "N/A",
                            "unit": material.unit or "N/A",
                            "current_balance": closing,
                            "opening_balance": opening,
                            "total_received": act["received"],
                            "received_value": act["received_val"],
                            "total_used": act["used"],
                            "used_value": act["used_val"],
                            "total_returned_supplier": act["returned_supplier"],
                            "total_transfer_in": act["transfer_in"],
                            "total_transfer_out": act["transfer_out"],
                            "has_negative_balance": closing < 0,
                            "supplier_name": sup,
                            "invoice_no": inv,
                            "invoice_date": act["invoice_date"],
                            "last_updated": updated_dt
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
