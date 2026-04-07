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
    def get_site_stock_summary(db: Session, site_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Dict[str, Any]]:
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
                        "received_value": Decimal('0.00'),
                        "total_used": Decimal('0.00'),
                        "used_value": Decimal('0.00'),
                        "total_returned_supplier": Decimal('0.00'),
                        "total_transfer_in": Decimal('0.00'),
                        "total_transfer_out": Decimal('0.00'),
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
                    day_received_value = Decimal('0.00')
                    day_used = Decimal('0.00')
                    day_used_value = Decimal('0.00')
                    day_returned_supplier = Decimal('0.00')
                    day_transfer_in = Decimal('0.00')
                    day_transfer_out = Decimal('0.00')
                    latest_in_day = None
                    
                    for e, safe_date in daily_data:
                        if latest_in_day is None or safe_date > latest_in_day:
                            latest_in_day = safe_date
                            
                        entry_cost = e.total_cost or Decimal('0.00')
                            
                        if e.entry_type == 'received':
                            day_received += e.quantity
                            day_received_value += entry_cost
                        elif e.entry_type == 'used':
                            if e.remarks and 'Transfer OUT' in e.remarks:
                                day_transfer_out += e.quantity
                            else:
                                day_used += e.quantity
                                day_used_value += entry_cost
                        elif e.entry_type == 'returned_received':
                            day_transfer_in += e.quantity
                        elif e.entry_type == 'returned_supplier':
                            day_returned_supplier += e.quantity
                            
                    closing_bal = opening_bal + day_received + day_transfer_in - day_used - day_transfer_out - day_returned_supplier
                    
                    summary.append({
                        "material_id": material.id,
                        "material_name": material.name,
                        "category": material.category.name if material.category else "N/A",
                        "unit": material.unit or "N/A",
                        "current_balance": closing_bal,
                        "opening_balance": opening_bal,
                        "total_received": day_received,
                        "received_value": day_received_value,
                        "total_used": day_used,
                        "used_value": day_used_value,
                        "total_returned_supplier": day_returned_supplier,
                        "total_transfer_in": day_transfer_in,
                        "total_transfer_out": day_transfer_out,
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
                    "received_value": balance["received_value"],
                    "total_used": balance["total_used"],
                    "used_value": balance["used_value"],
                    "total_returned_supplier": balance["total_returned_supplier"],
                    "total_transfer_in": balance["total_transfer_in"],
                    "total_transfer_out": balance["total_transfer_out"],
                    "has_negative_balance": balance["has_negative_balance"],
                    "last_updated": latest_entry_date 
                })
        
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
