"""
Stock calculation utilities - Running Balance Ledger & FIFO Costing
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

            if not entries and not is_daily_report: continue

            # Standard cost fallback in case of negative stock consumption
            mat_standard_cost = material.standard_cost or Decimal('0.0')

            lots = [] 
            global_running_balance = Decimal('0.0')
            entries_by_date = {}

            for e in entries:
                safe_date = e.entry_date.replace(tzinfo=None) if getattr(e.entry_date, 'tzinfo', None) else e.entry_date
                d = safe_date.date()
                if d not in entries_by_date: entries_by_date[d] = []
                entries_by_date[d].append(e)

            sorted_dates = sorted(entries_by_date.keys())
            if is_daily_report and effective_end not in entries_by_date:
                sorted_dates.append(effective_end)
                entries_by_date[effective_end] = []

            for current_date in sorted_dates:
                opening_balance_today = global_running_balance
                daily_receipt_rows = []
                
                total_used_today = Decimal('0.0')
                total_used_val_today = Decimal('0.0')
                total_t_out_today = Decimal('0.0')
                total_t_in_today = Decimal('0.0')
                total_ret_sup_today = Decimal('0.0')

                # FIX: Sort same-day entries so 'Received' processes BEFORE 'Used' to prevent ₹0.00 costs
                daily_entries = entries_by_date.get(current_date, [])
                daily_entries.sort(key=lambda x: 0 if x.entry_type in ['received', 'returned_received'] else 1)

                for e in daily_entries:
                    if e.entry_type in ['received', 'returned_received']:
                        qty = e.quantity
                        cost = e.total_cost or Decimal('0.0')
                        global_running_balance += qty 
                        
                        if e.entry_type == 'received':
                            daily_receipt_rows.append({
                                "material_id": material.id, "material_name": material.name,
                                "category": material.category.name if material.category else "N/A",
                                "unit": material.unit or "N/A",
                                "current_balance": global_running_balance, 
                                "opening_balance": global_running_balance - qty,
                                "total_received": qty, "received_value": cost,
                                "total_used": 0, "used_value": 0,
                                "total_returned_supplier": 0, "total_transfer_in": 0, "total_transfer_out": 0,
                                "has_negative_balance": global_running_balance < 0,
                                "supplier_name": e.supplier_name or '-', 
                                "invoice_no": e.invoice_no or '-', 
                                "invoice_date": e.invoice_date,
                                "last_updated": datetime.combine(current_date, time(10,0,0))
                            })
                            u_cost = (cost / qty) if qty > 0 else Decimal('0.0')
                            lots.append({"qty": qty, "u_cost": u_cost})
                        else:
                            total_t_in_today += qty
                            lots.append({"qty": qty, "u_cost": mat_standard_cost})
                            
                    elif e.entry_type in ['used', 'returned_supplier']:
                        qty_to_consume = e.quantity
                        global_running_balance -= qty_to_consume
                        
                        # FIFO Depletion
                        for lot in lots:
                            if qty_to_consume <= 0: break
                            if lot["qty"] > 0:
                                deduct = min(lot["qty"], qty_to_consume)
                                lot["qty"] -= deduct
                                qty_to_consume -= deduct
                                if e.entry_type == 'used':
                                    if e.remarks and 'Transfer OUT' in e.remarks: 
                                        total_t_out_today += deduct
                                    else:
                                        total_used_today += deduct
                                        total_used_val_today += deduct * lot["u_cost"]
                                else: 
                                    total_ret_sup_today += deduct
                        
                        # FALLBACK: If consumption exceeds known lots, use material's standard cost
                        if qty_to_consume > 0:
                            if e.entry_type == 'used':
                                if e.remarks and 'Transfer OUT' in e.remarks: 
                                    total_t_out_today += qty_to_consume
                                else: 
                                    total_used_today += qty_to_consume
                                    total_used_val_today += qty_to_consume * mat_standard_cost
                            else: 
                                total_ret_sup_today += qty_to_consume

                # Generate rows if within filter range
                if effective_start <= current_date <= effective_end:
                    for row in daily_receipt_rows:
                        summary.append(row)

                    has_movement = (total_used_today > 0 or total_t_out_today > 0 or total_t_in_today > 0 or total_ret_sup_today > 0)
                    if has_movement:
                        summary.append({
                            "material_id": material.id, "material_name": material.name,
                            "category": material.category.name if material.category else "N/A",
                            "unit": material.unit or "N/A",
                            "current_balance": global_running_balance, 
                            "opening_balance": global_running_balance + total_used_today + total_t_out_today + total_ret_sup_today - total_t_in_today,
                            "total_received": 0, "received_value": 0,
                            "total_used": total_used_today, "used_value": total_used_val_today,
                            "total_returned_supplier": total_ret_sup_today,
                            "total_transfer_in": total_t_in_today, "total_transfer_out": total_t_out_today,
                            "has_negative_balance": global_running_balance < 0,
                            "supplier_name": "CONSOLIDATED MOVEMENT", "invoice_no": "-", "invoice_date": None,
                            "last_updated": datetime.combine(current_date, time(13,0,0))
                        })

                    if is_daily_report and not daily_receipt_rows and not has_movement:
                        summary.append({
                            "material_id": material.id, "material_name": material.name,
                            "category": material.category.name if material.category else "N/A",
                            "unit": material.unit or "N/A",
                            "current_balance": global_running_balance,
                            "opening_balance": global_running_balance,
                            "total_received": 0, "received_value": 0, "total_used": 0, "used_value": 0,
                            "total_returned_supplier": 0, "total_transfer_in": 0, "total_transfer_out": 0,
                            "has_negative_balance": global_running_balance < 0,
                            "supplier_name": "-", "invoice_no": "-", "invoice_date": None,
                            "last_updated": datetime.combine(current_date, time(23,59,0))
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
                aggregated[mat_id]["total_received"] += item["total_received"]
                aggregated[mat_id]["received_value"] += item["received_value"]
                aggregated[mat_id]["total_used"] += item["total_used"]
                aggregated[mat_id]["used_value"] += item["used_value"]
                aggregated[mat_id]["total_returned_supplier"] += item["total_returned_supplier"]
                aggregated[mat_id]["total_transfer_in"] += item["total_transfer_in"]
                aggregated[mat_id]["total_transfer_out"] += item["total_transfer_out"]
                aggregated[mat_id]["current_balance"] = item["current_balance"] 

        for mat_id, item in aggregated.items():
            existing_report = db.query(models.DailyStockReport).filter(
                models.DailyStockReport.site_id == site_id,
                models.DailyStockReport.material_id == mat_id,
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

# CLI helpers must remain outside the class
def cli_calculate_stock(db: Session, site_id: int, material_id: int):
    return StockCalculator().calculate_balance(db, site_id, material_id)

def cli_generate_daily_report(db: Session, site_id: int, report_date: date):
    return StockCalculator().generate_daily_report(db, site_id, report_date)
