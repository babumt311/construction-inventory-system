"""
Report generation utilities
"""
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, asc
import logging
import io
from fastapi.responses import StreamingResponse
from app import models, schemas, crud

logger = logging.getLogger(__name__)

class ReportGenerator:
    """Generate various reports for the inventory system"""
    
    @staticmethod
    def generate_material_wise_report(
        db: Session,
        project_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate material-wise report
        
        Columns:
        - Category
        - Material
        - Quantity
        - Unit
        - Cost
        - Total Cost
        """
        logger.info(f"Generating material-wise report for project {project_id}")
        
        query = db.query(
            models.Category.name.label("category"),
            models.Material.name.label("material"),
            models.Material.unit,
            func.sum(models.POEntry.quantity).label("quantity"),
            func.avg(models.POEntry.unit_price).label("unit_cost"),
            func.sum(models.POEntry.total_cost).label("total_cost")
        ).join(
            models.POEntry, models.POEntry.material_id == models.Material.id
        ).join(
            models.Category, models.Category.id == models.Material.category_id
        )
        
        # Apply filters
        if project_id:
            query = query.filter(models.POEntry.project_id == project_id)
        
        if start_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            query = query.filter(models.POEntry.po_date >= start_datetime)
        
        if end_date:
            end_datetime = datetime.combine(end_date, datetime.max.time())
            query = query.filter(models.POEntry.po_date <= end_datetime)
        
        # Group by material and category
        query = query.group_by(
            models.Category.name,
            models.Material.name,
            models.Material.unit
        ).order_by(
            models.Category.name,
            models.Material.name
        )
        
        results = query.all()
        
        report_data = []
        for row in results:
            report_data.append({
                "category": row.category,
                "material": row.material,
                "quantity": row.quantity or Decimal('0.00'),
                "unit": row.unit or "N/A",
                "unit_cost": row.unit_cost or Decimal('0.00'),
                "total_cost": row.total_cost or Decimal('0.00')
            })
        
        logger.debug(f"Generated material-wise report with {len(report_data)} rows")
        return report_data
    
    @staticmethod
    def generate_supplier_wise_report(
        db: Session,
        project_id: Optional[int] = None,
        supplier_name: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate supplier-wise report
        
        Columns:
        - Supplier Name
        - Material
        - Quantity
        - Unit
        - Total Cost
        - Invoice No
        - Purchase Date
        """
        logger.info(f"Generating supplier-wise report for project {project_id}")
        
        query = db.query(
            models.POEntry.supplier_name,
            models.Material.name.label("material"),
            models.Material.unit,
            models.POEntry.quantity,
            models.POEntry.total_cost,
            models.POEntry.invoice_no,
            models.POEntry.po_date.label("purchase_date")
        ).join(
            models.Material, models.Material.id == models.POEntry.material_id
        )
        
        # Apply filters
        if project_id:
            query = query.filter(models.POEntry.project_id == project_id)
        
        if supplier_name:
            query = query.filter(models.POEntry.supplier_name.ilike(f"%{supplier_name}%"))
        
        if start_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            query = query.filter(models.POEntry.po_date >= start_datetime)
        
        if end_date:
            end_datetime = datetime.combine(end_date, datetime.max.time())
            query = query.filter(models.POEntry.po_date <= end_datetime)
        
        query = query.order_by(
            models.POEntry.supplier_name,
            models.POEntry.po_date.desc()
        )
        
        results = query.all()
        
        report_data = []
        for row in results:
            report_data.append({
                "supplier_name": row.supplier_name,
                "material": row.material,
                "quantity": row.quantity,
                "unit": row.unit or "N/A",
                "total_cost": row.total_cost,
                "invoice_no": row.invoice_no,
                "purchase_date": row.purchase_date
            })
        
        logger.debug(f"Generated supplier-wise report with {len(report_data)} rows")
        return report_data
    
    @staticmethod
    def generate_period_report(
        db: Session,
        site_id: int,
        start_date: date,
        end_date: date,
        material_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate period report (Weekly/Monthly/Annual)
        
        Columns:
        - Material
        - Unit
        - Opening Stock
        - Received
        - Total Issued
        - Returned
        - Closing Stock
        - Remarks
        """
        logger.info(f"Generating period report for site {site_id} from {start_date} to {end_date}")
        
        # Get all materials for the site in the period
        materials_query = db.query(models.Material).distinct().join(
            models.DailyStockReport
        ).filter(
            models.DailyStockReport.site_id == site_id,
            models.DailyStockReport.report_date >= datetime.combine(start_date, datetime.min.time()),
            models.DailyStockReport.report_date <= datetime.combine(end_date, datetime.max.time())
        )
        
        if material_id:
            materials_query = materials_query.filter(models.Material.id == material_id)
        
        materials = materials_query.all()
        
        report_data = []
        
        for material in materials:
            # Get reports for this material in the period
            reports = db.query(models.DailyStockReport).filter(
                models.DailyStockReport.site_id == site_id,
                models.DailyStockReport.material_id == material.id,
                models.DailyStockReport.report_date >= datetime.combine(start_date, datetime.min.time()),
                models.DailyStockReport.report_date <= datetime.combine(end_date, datetime.max.time())
            ).order_by(models.DailyStockReport.report_date).all()
            
            if not reports:
                continue
            
            # Get opening stock from first report
            opening_stock = reports[0].opening_stock
            
            # Calculate totals for the period
            total_received = Decimal('0.00')
            total_used = Decimal('0.00')
            total_returned = Decimal('0.00')
            
            for report in reports:
                total_received += report.received
                total_used += report.used
                total_returned += report.returned_received
            
            # Get closing stock from last report
            closing_stock = reports[-1].closing_stock
            
            # Calculate total issued (used - returned)
            total_issued = total_used - total_returned
            
            report_data.append({
                "material": material.name,
                "unit": material.unit or "N/A",
                "opening_stock": opening_stock,
                "received": total_received,
                "total_issued": total_issued,
                "returned": total_returned,
                "closing_stock": closing_stock,
                "remarks": f"Period: {start_date} to {end_date}"
            })
        
        logger.debug(f"Generated period report with {len(report_data)} materials")
        return report_data
    
    @staticmethod
    def generate_custom_report(
        db: Session,
        filters: schemas.ReportFilter
    ) -> List[Dict[str, Any]]:
        """
        Generate custom report based on filters
        """
        logger.info(f"Generating custom report with filters: {filters.dict()}")
        
        # This is a flexible report that can combine different data
        # Based on the filters provided
        
        report_data = []
        
        # Determine report type based on filters
        if filters.material_id or filters.category_id:
            # Material-focused report
            report_data = ReportGenerator.generate_material_wise_report(
                db, filters.project_id, filters.start_date, filters.end_date
            )
            
            # Apply additional filtering
            if filters.material_id:
                report_data = [row for row in report_data 
                             if any(str(filters.material_id) in str(value) 
                                   for value in row.values())]
        
        elif filters.supplier_name:
            # Supplier-focused report
            report_data = ReportGenerator.generate_supplier_wise_report(
                db, filters.project_id, filters.supplier_name,
                filters.start_date, filters.end_date
            )
        
        elif filters.site_id:
            # Site-focused report (stock movement)
            if filters.start_date and filters.end_date:
                report_data = ReportGenerator.generate_period_report(
                    db, filters.site_id, filters.start_date, filters.end_date,
                    filters.material_id
                )
        
        logger.debug(f"Generated custom report with {len(report_data)} rows")
        return report_data
    
    @staticmethod
    def generate_supplier_summary_report(
        db: Session,
        project_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate supplier summary report
        
        Columns:
        - Supplier
        - Total Cost
        - Invoice Count
        - Last Purchase Date
        """
        logger.info(f"Generating supplier summary report for project {project_id}")
        
        query = db.query(
            models.POEntry.supplier_name,
            func.sum(models.POEntry.total_cost).label("total_cost"),
            func.count(models.POEntry.id).label("invoice_count"),
            func.max(models.POEntry.po_date).label("last_purchase_date")
        )
        
        if project_id:
            query = query.filter(models.POEntry.project_id == project_id)
        
        query = query.group_by(
            models.POEntry.supplier_name
        ).order_by(
            desc("total_cost")
        )
        
        results = query.all()
        
        report_data = []
        for row in results:
            report_data.append({
                "supplier": row.supplier_name,
                "total_cost": row.total_cost or Decimal('0.00'),
                "invoice_count": row.invoice_count or 0,
                "last_purchase_date": row.last_purchase_date
            })
        
        logger.debug(f"Generated supplier summary report with {len(report_data)} suppliers")
        return report_data
    
    @staticmethod
    def export_to_excel(
        report_data: List[Dict[str, Any]],
        report_type: str
    ) -> StreamingResponse:
        """
        Export report data to Excel
        """
        logger.info(f"Exporting {report_type} report to Excel")
        
        # Convert to DataFrame
        df = pd.DataFrame(report_data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Report')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Report']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_report_{timestamp}.xlsx"
        
        logger.debug(f"Excel export completed: {filename}")
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    @staticmethod
    def generate_stock_valuation_report(
        db: Session,
        site_id: Optional[int] = None,
        project_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate stock valuation report
        
        Columns:
        - Material
        - Category
        - Unit
        - Current Stock
        - Unit Cost
        - Total Value
        """
        logger.info(f"Generating stock valuation report")
        
        from app.utils.stock_calculator import StockCalculator
        
        # Get materials with stock
        materials_query = db.query(models.Material)
        
        if project_id and not site_id:
            # Get all sites for the project
            sites = db.query(models.Site).filter(models.Site.project_id == project_id).all()
            site_ids = [site.id for site in sites]
        elif site_id:
            site_ids = [site_id]
        else:
            site_ids = []
        
        calculator = StockCalculator()
        report_data = []
        
        for material in materials_query.all():
            total_stock = Decimal('0.00')
            
            if site_ids:
                for site_id in site_ids:
                    balance = calculator.calculate_balance(db, site_id, material.id)
                    total_stock += balance["current_balance"]
            else:
                # Get all sites with this material
                sites_with_material = db.query(models.StockEntry.site_id).filter(
                    models.StockEntry.material_id == material.id
                ).distinct().all()
                
                for site_tuple in sites_with_material:
                    site_id = site_tuple[0]
                    balance = calculator.calculate_balance(db, site_id, material.id)
                    total_stock += balance["current_balance"]
            
            if total_stock > Decimal('0.00'):
                # Get average unit cost from PO entries
                avg_cost_query = db.query(func.avg(models.POEntry.unit_price)).filter(
                    models.POEntry.material_id == material.id
                )
                
                avg_cost = avg_cost_query.scalar() or Decimal('0.00')
                total_value = total_stock * avg_cost
                
                report_data.append({
                    "material": material.name,
                    "category": material.category.name if material.category else "N/A",
                    "unit": material.unit or "N/A",
                    "current_stock": total_stock,
                    "unit_cost": avg_cost,
                    "total_value": total_value
                })
        
        # Sort by total value (descending)
        report_data.sort(key=lambda x: x["total_value"], reverse=True)
        
        logger.debug(f"Generated stock valuation report with {len(report_data)} items")
        return report_data

# CLI functions for report generation
def cli_generate_report(db: Session, report_type: str, **kwargs):
    """CLI function to generate reports"""
    print(f"📊 Generating {report_type} report...")
    
    generator = ReportGenerator()
    report_data = []
    
    if report_type == "material-wise":
        report_data = generator.generate_material_wise_report(
            db, kwargs.get('project_id')
        )
    elif report_type == "supplier-wise":
        report_data = generator.generate_supplier_wise_report(
            db, kwargs.get('project_id'), kwargs.get('supplier_name')
        )
    elif report_type == "supplier-summary":
        report_data = generator.generate_supplier_summary_report(
            db, kwargs.get('project_id')
        )
    elif report_type == "stock-valuation":
        report_data = generator.generate_stock_valuation_report(
            db, kwargs.get('site_id'), kwargs.get('project_id')
        )
    
    print(f"✅ Generated {len(report_data)} rows")
    
    # Display first few rows
    if report_data:
        print("\n📋 Sample data:")
        for i, row in enumerate(report_data[:5]):
            print(f"  Row {i+1}: {list(row.items())[:3]}...")
    
    return report_data
