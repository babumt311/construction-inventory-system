"""
Excel/CSV file processing utilities
"""
import pandas as pd
from typing import Dict, List, Any, Tuple
import logging
from datetime import datetime
from decimal import Decimal
import os
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas, crud
from app.config import settings

logger = logging.getLogger(__name__)

class ExcelProcessor:
    """Process Excel/CSV files for data import"""
    
    # Define expected column names for material upload
    MATERIAL_COLUMNS = {
        "required": ["category", "material_name", "unit"],
        "optional": ["description", "standard_cost"]
    }
    
    @staticmethod
    def validate_file(file: UploadFile) -> Tuple[bool, str]:
        """Validate uploaded file"""
        logger.debug(f"Validating uploaded file: {file.filename}")
        
        # Check file extension
        filename = file.filename.lower()
        valid_extensions = ['.xlsx', '.xls', '.csv']
        
        if not any(filename.endswith(ext) for ext in valid_extensions):
            error_msg = f"Invalid file type. Allowed: {', '.join(valid_extensions)}"
            logger.error(error_msg)
            return False, error_msg
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset pointer
        
        if file_size > settings.MAX_UPLOAD_SIZE:
            error_msg = f"File too large. Max size: {settings.MAX_UPLOAD_SIZE/1024/1024}MB"
            logger.error(error_msg)
            return False, error_msg
        
        logger.debug(f"File validation passed: {file.filename}")
        return True, "File validation passed"
    
    @staticmethod
    def process_material_file(
        db: Session,
        file: UploadFile,
        update_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Process material data from Excel/CSV file
        
        Expected columns:
        - category (required): Material category
        - material_name (required): Name of material
        - unit (required): Unit of measurement
        - description (optional): Material description
        - standard_cost (optional): Standard cost
        """
        logger.info(f"Processing material file: {file.filename}")
        
        results = {
            "rows_processed": 0,
            "rows_successful": 0,
            "rows_failed": 0,
            "errors": [],
            "materials_created": [],
            "materials_updated": []
        }
        
        try:
            # Read file based on extension
            filename = file.filename.lower()
            
            if filename.endswith('.csv'):
                df = pd.read_csv(file.file)
            else:  # Excel files
                df = pd.read_excel(file.file)
            
            logger.debug(f"File loaded successfully. Rows: {len(df)}, Columns: {df.columns.tolist()}")
            
            # Validate columns
            missing_columns = []
            for col in ExcelProcessor.MATERIAL_COLUMNS["required"]:
                if col not in df.columns:
                    missing_columns.append(col)
            
            if missing_columns:
                error_msg = f"Missing required columns: {', '.join(missing_columns)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                return results
            
            # Process each row
            for index, row in df.iterrows():
                results["rows_processed"] += 1
                row_num = index + 2  # +2 for header row and 0-based index
                
                try:
                    # Extract and clean data
                    category_name = str(row["category"]).strip()
                    material_name = str(row["material_name"]).strip()
                    unit = str(row["unit"]).strip() if pd.notna(row.get("unit")) else None
                    
                    description = None
                    if "description" in df.columns and pd.notna(row.get("description")):
                        description = str(row["description"]).strip()
                    
                    standard_cost = Decimal('0.00')
                    if "standard_cost" in df.columns and pd.notna(row.get("standard_cost")):
                        try:
                            standard_cost = Decimal(str(row["standard_cost"]))
                        except:
                            standard_cost = Decimal('0.00')
                    
                    # Validate required fields
                    if not category_name or not material_name:
                        error_msg = f"Row {row_num}: Missing required fields"
                        results["errors"].append(error_msg)
                        results["rows_failed"] += 1
                        continue
                    
                    # Find or create category
                    category = crud.crud_category.get_by_name(db, name=category_name)
                    if not category:
                        category = models.Category(name=category_name)
                        db.add(category)
                        db.commit()
                        db.refresh(category)
                        logger.debug(f"Created new category: {category_name}")
                    
                    # Check if material exists
                    existing_material = db.query(models.Material).filter(
                        models.Material.name == material_name,
                        models.Material.category_id == category.id
                    ).first()
                    
                    if existing_material:
                        if update_existing:
                            # Update existing material
                            if unit:
                                existing_material.unit = unit
                            if description:
                                existing_material.description = description
                            if standard_cost > Decimal('0.00'):
                                existing_material.standard_cost = standard_cost
                            
                            db.add(existing_material)
                            results["materials_updated"].append(material_name)
                            logger.debug(f"Updated material: {material_name}")
                        else:
                            logger.debug(f"Skipping existing material: {material_name}")
                            results["rows_successful"] += 1
                            continue
                    else:
                        # Create new material
                        material = models.Material(
                            name=material_name,
                            category_id=category.id,
                            unit=unit,
                            description=description,
                            standard_cost=standard_cost
                        )
                        db.add(material)
                        results["materials_created"].append(material_name)
                        logger.debug(f"Created new material: {material_name}")
                    
                    results["rows_successful"] += 1
                    
                except Exception as e:
                    error_msg = f"Row {row_num}: Error processing - {str(e)}"
                    results["errors"].append(error_msg)
                    results["rows_failed"] += 1
                    logger.error(f"Error processing row {row_num}: {str(e)}")
            
            db.commit()
            logger.info(f"Material file processing completed. Successful: {results['rows_successful']}, Failed: {results['rows_failed']}")
            
        except Exception as e:
            error_msg = f"Error processing file: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(f"File processing error: {str(e)}")
            db.rollback()
        
        return results
    
    @staticmethod
    def generate_material_template() -> bytes:
        """Generate Excel template for material upload"""
        logger.debug("Generating material upload template")
        
        # Create sample data
        data = {
            "category": ["Electrical", "Electrical", "Plumbing"],
            "material_name": ["Wire 2.5mm", "Switch", "PVC Pipe 2inch"],
            "unit": ["meter", "piece", "meter"],
            "description": ["Copper wire 2.5mm", "Single pole switch", "PVC pipe 2 inch diameter"],
            "standard_cost": [150.00, 25.50, 300.00]
        }
        
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = pd.ExcelWriter("material_template.xlsx", engine='openpyxl')
        df.to_excel(output, index=False, sheet_name='Materials')
        
        # Get the workbook and worksheet
        workbook = output.book
        worksheet = output.sheets['Materials']
        
        # Add formatting/instructions
        from openpyxl.styles import Font, PatternFill
        
        # Style header
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        
        for cell in worksheet[1]:
            cell.font = header_font
            cell.fill = header_fill
        
        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 30)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.close()
        
        # Read file back as bytes
        with open("material_template.xlsx", "rb") as f:
            template_bytes = f.read()
        
        # Clean up
        if os.path.exists("material_template.xlsx"):
            os.remove("material_template.xlsx")
        
        logger.debug("Material template generated successfully")
        return template_bytes
    
    @staticmethod
    def process_stock_entry_file(
        db: Session,
        file: UploadFile,
        site_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Process stock entry data from Excel/CSV file
        
        Expected columns:
        - material_name (required): Name of material
        - entry_type (required): received/used/returned_received/returned_supplier
        - quantity (required): Quantity
        - supplier_name (optional): Supplier name
        - invoice_no (optional): Invoice number
        - reference (optional): Reference number
        - remarks (optional): Remarks
        - entry_date (optional): Entry date (defaults to current date)
        """
        logger.info(f"Processing stock entry file for site {site_id}")
        
        results = {
            "rows_processed": 0,
            "rows_successful": 0,
            "rows_failed": 0,
            "errors": [],
            "entries_created": []
        }
        
        try:
            # Read file
            filename = file.filename.lower()
            
            if filename.endswith('.csv'):
                df = pd.read_csv(file.file)
            else:
                df = pd.read_excel(file.file)
            
            # Required columns
            required_columns = ["material_name", "entry_type", "quantity"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                error_msg = f"Missing required columns: {', '.join(missing_columns)}"
                results["errors"].append(error_msg)
                return results
            
            # Process each row
            for index, row in df.iterrows():
                results["rows_processed"] += 1
                row_num = index + 2
                
                try:
                    material_name = str(row["material_name"]).strip()
                    entry_type = str(row["entry_type"]).strip().lower()
                    quantity_str = str(row["quantity"])
                    
                    # Parse quantity
                    try:
                        quantity = Decimal(quantity_str)
                        if quantity <= Decimal('0.00'):
                            raise ValueError("Quantity must be positive")
                    except:
                        error_msg = f"Row {row_num}: Invalid quantity '{quantity_str}'"
                        results["errors"].append(error_msg)
                        results["rows_failed"] += 1
                        continue
                    
                    # Validate entry type
                    valid_types = ["received", "used", "returned_received", "returned_supplier"]
                    if entry_type not in valid_types:
                        error_msg = f"Row {row_num}: Invalid entry type '{entry_type}'. Valid: {', '.join(valid_types)}"
                        results["errors"].append(error_msg)
                        results["rows_failed"] += 1
                        continue
                    
                    # Find material
                    material = db.query(models.Material).filter(
                        models.Material.name.ilike(f"%{material_name}%")
                    ).first()
                    
                    if not material:
                        error_msg = f"Row {row_num}: Material '{material_name}' not found"
                        results["errors"].append(error_msg)
                        results["rows_failed"] += 1
                        continue
                    
                    # Extract optional fields
                    supplier_name = None
                    if "supplier_name" in df.columns and pd.notna(row.get("supplier_name")):
                        supplier_name = str(row["supplier_name"]).strip()
                    
                    invoice_no = None
                    if "invoice_no" in df.columns and pd.notna(row.get("invoice_no")):
                        invoice_no = str(row["invoice_no"]).strip()
                    
                    reference = None
                    if "reference" in df.columns and pd.notna(row.get("reference")):
                        reference = str(row["reference"]).strip()
                    
                    remarks = None
                    if "remarks" in df.columns and pd.notna(row.get("remarks")):
                        remarks = str(row["remarks"]).strip()
                    
                    entry_date = datetime.now()
                    if "entry_date" in df.columns and pd.notna(row.get("entry_date")):
                        try:
                            entry_date = pd.to_datetime(row["entry_date"]).to_pydatetime()
                        except:
                            pass  # Use current date if parsing fails
                    
                    # Create stock entry
                    stock_entry = models.StockEntry(
                        site_id=site_id,
                        material_id=material.id,
                        entry_type=entry_type,
                        quantity=quantity,
                        supplier_name=supplier_name,
                        invoice_no=invoice_no,
                        reference=reference,
                        remarks=remarks,
                        entry_date=entry_date,
                        created_by=user_id
                    )
                    
                    db.add(stock_entry)
                    results["entries_created"].append({
                        "material": material_name,
                        "type": entry_type,
                        "quantity": quantity
                    })
                    results["rows_successful"] += 1
                    
                    logger.debug(f"Created stock entry: {material_name} - {entry_type} - {quantity}")
                    
                except Exception as e:
                    error_msg = f"Row {row_num}: Error - {str(e)}"
                    results["errors"].append(error_msg)
                    results["rows_failed"] += 1
            
            db.commit()
            logger.info(f"Stock entry file processing completed. Successful: {results['rows_successful']}")
            
        except Exception as e:
            error_msg = f"Error processing file: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(f"Stock file processing error: {str(e)}")
            db.rollback()
        
        return results

# CLI functions for Excel operations
def cli_generate_template():
    """CLI function to generate material template"""
    print("📄 Generating material upload template...")
    
    processor = ExcelProcessor()
    template_bytes = processor.generate_material_template()
    
    # Save template to file
    template_path = "material_upload_template.xlsx"
    with open(template_path, "wb") as f:
        f.write(template_bytes)
    
    print(f"✅ Template generated: {template_path}")
    print("📋 Template columns:")
    print("  - category (required): Material category")
    print("  - material_name (required): Name of material")
    print("  - unit (required): Unit of measurement")
    print("  - description (optional): Material description")
    print("  - standard_cost (optional): Standard cost")
    
    return template_path

def cli_validate_file_format(file_path: str):
    """CLI function to validate file format"""
    print(f"🔍 Validating file format: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    try:
        # Try to read the file
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        print(f"✅ File loaded successfully")
        print(f"   Rows: {len(df)}")
        print(f"   Columns: {', '.join(df.columns.tolist())}")
        
        # Check required columns for materials
        required = ExcelProcessor.MATERIAL_COLUMNS["required"]
        missing = [col for col in required if col not in df.columns]
        
        if missing:
            print(f"❌ Missing required columns: {', '.join(missing)}")
            return False
        
        print("✅ All required columns present")
        
        # Show sample data
        print("\n📋 Sample data (first 3 rows):")
        print(df.head(3).to_string())
        
        return True
        
    except Exception as e:
        print(f"❌ Error reading file: {str(e)}")
        return False
