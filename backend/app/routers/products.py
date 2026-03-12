"""
Products (Materials and Categories) router
"""

# Add to any router file if these imports are missing
from app.auth import check_project_access
from app.auth import get_admin_user_dependency  # Add this function if missing
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
import logging
from app import schemas, crud, models
from app.database import get_db
from app.dependencies import (
    get_owner_or_admin_user_dependency,
    get_current_user_dependency,
    PaginationParams,
    log_audit_action
)
from app.utils.excel_processor import ExcelProcessor

router = APIRouter(prefix="/products", tags=["products"])
logger = logging.getLogger(__name__)

# Categories endpoints
@router.get("/categories", response_model=List[schemas.CategoryInDB])
async def read_categories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Retrieve all categories
    """
    logger.debug("Reading all categories")
    categories = crud.crud_category.get_multi(db)
    return categories

@router.post("/categories", response_model=schemas.CategoryInDB)
async def create_category(
    category_in: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Create new category (Owner/Admin only)
    """
    logger.info(f"Creating new category: {category_in.name} by {current_user.username}")
    
    # Check if category already exists
    existing_category = crud.crud_category.get_by_name(db, name=category_in.name)
    if existing_category:
        logger.warning(f"Category already exists: {category_in.name}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category already exists"
        )
    
    category = crud.crud_category.create(db, obj_in=category_in)
    
    logger.info(f"Category created successfully: {category.name} (ID: {category.id})")
    return category

@router.put("/categories/{category_id}", response_model=schemas.CategoryInDB)
async def update_category(
    category_id: int,
    category_in: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Update category (Owner/Admin only)
    """
    logger.info(f"Updating category ID: {category_id} by {current_user.username}")
    
    category = crud.crud_category.get(db, id=category_id)
    
    if not category:
        logger.warning(f"Category not found for update: {category_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Check if new name already exists
    if category_in.name and category_in.name != category.name:
        existing_category = crud.crud_category.get_by_name(db, name=category_in.name)
        if existing_category:
            logger.warning(f"Category name already exists: {category_in.name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category name already exists"
            )
    
    updated_category = crud.crud_category.update(db, db_obj=category, obj_in=category_in)
    
    logger.info(f"Category updated successfully: {updated_category.name}")
    return updated_category

@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Delete category (Owner/Admin only)
    """
    logger.info(f"Deleting category ID: {category_id} by {current_user.username}")
    
    # Check if category has materials
    category = crud.crud_category.get_with_materials(db, category_id)
    if category and category.materials:
        logger.warning(f"Cannot delete category with materials: {category_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category that has materials. Remove materials first."
        )
    
    deleted_category = crud.crud_category.delete(db, id=category_id)
    
    if not deleted_category:
        logger.warning(f"Category not found for deletion: {category_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    logger.info(f"Category deleted successfully: ID {category_id}")
    return {"message": "Category deleted successfully"}

# Materials endpoints
@router.get("/materials", response_model=List[schemas.MaterialInDB])
async def read_materials(
    pagination: PaginationParams = Depends(),
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Retrieve materials with optional filtering
    """
    logger.debug("Reading materials")
    
    query = db.query(models.Material)
    
    # Apply filters
    if category_id:
        query = query.filter(models.Material.category_id == category_id)
    
    if search:
        query = query.filter(models.Material.name.ilike(f"%{search}%"))
    
    # Apply sorting
    if pagination.sort_by:
        if hasattr(models.Material, pagination.sort_by):
            if pagination.sort_order == "desc":
                query = query.order_by(getattr(models.Material, pagination.sort_by).desc())
            else:
                query = query.order_by(getattr(models.Material, pagination.sort_by).asc())
    else:
        query = query.order_by(models.Material.name)
    
    # Apply pagination
    materials = query.offset(pagination.skip).limit(pagination.size).all()
    
    logger.debug(f"Returning {len(materials)} materials")
    return materials

@router.get("/materials/search")
async def search_materials(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_dependency)
) -> Any:
    """
    Search materials by name
    """
    logger.debug(f"Searching materials for query: {q}")
    
    materials = crud.crud_material.search(db, search_term=q)
    
    # Limit results
    if limit:
        materials = materials[:limit]
    
    logger.debug(f"Found {len(materials)} materials")
    return materials

@router.post("/materials", response_model=schemas.MaterialInDB)
async def create_material(
    material_in: schemas.MaterialCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Create new material (Owner/Admin only)
    """
    logger.info(f"Creating new material: {material_in.name} by {current_user.username}")
    
    # Check if material already exists in this category
    existing_material = db.query(models.Material).filter(
        models.Material.name == material_in.name,
        models.Material.category_id == material_in.category_id
    ).first()
    
    if existing_material:
        logger.warning(f"Material already exists in category: {material_in.name}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Material already exists in this category"
        )
    
    # Verify category exists
    category = crud.crud_category.get(db, id=material_in.category_id)
    if not category:
        logger.warning(f"Category not found: {material_in.category_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category not found"
        )
    
    material = crud.crud_material.create(db, obj_in=material_in)
    
    logger.info(f"Material created successfully: {material.name} (ID: {material.id})")
    return material

@router.put("/materials/{material_id}", response_model=schemas.MaterialInDB)
async def update_material(
    material_id: int,
    material_in: schemas.MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Update material (Owner/Admin only)
    """
    logger.info(f"Updating material ID: {material_id} by {current_user.username}")
    
    material = crud.crud_material.get(db, id=material_id)
    
    if not material:
        logger.warning(f"Material not found for update: {material_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    # Check if new name already exists in category
    if material_in.name and material_in.name != material.name:
        existing_material = db.query(models.Material).filter(
            models.Material.name == material_in.name,
            models.Material.category_id == material.category_id
        ).first()
        
        if existing_material:
            logger.warning(f"Material name already exists in category: {material_in.name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Material name already exists in this category"
            )
    
    updated_material = crud.crud_material.update(db, db_obj=material, obj_in=material_in)
    
    logger.info(f"Material updated successfully: {updated_material.name}")
    return updated_material

@router.delete("/materials/{material_id}")
async def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Delete material (Owner/Admin only)
    """
    logger.info(f"Deleting material ID: {material_id} by {current_user.username}")
    
    # Check if material is used in stock entries or PO entries
    material = crud.crud_material.get(db, id=material_id)
    if not material:
        logger.warning(f"Material not found for deletion: {material_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    # Check stock entries
    stock_entries = db.query(models.StockEntry).filter(
        models.StockEntry.material_id == material_id
    ).count()
    
    if stock_entries > 0:
        logger.warning(f"Cannot delete material with stock entries: {material_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete material that has stock entries"
        )
    
    # Check PO entries
    po_entries = db.query(models.POEntry).filter(
        models.POEntry.material_id == material_id
    ).count()
    
    if po_entries > 0:
        logger.warning(f"Cannot delete material with PO entries: {material_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete material that has PO entries"
        )
    
    deleted_material = crud.crud_material.delete(db, id=material_id)
    
    logger.info(f"Material deleted successfully: ID {material_id}")
    return {"message": "Material deleted successfully"}

# Excel Upload endpoints
@router.post("/upload/materials", response_model=schemas.ExcelUploadResponse)
async def upload_materials_excel(
    file: UploadFile = File(...),
    update_existing: bool = True,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency),
    audit_log: dict = Depends(log_audit_action)
) -> Any:
    """
    Upload materials from Excel/CSV file (Owner/Admin only)
    """
    logger.info(f"Uploading materials file: {file.filename} by {current_user.username}")
    
    # Validate file
    is_valid, error_msg = ExcelProcessor.validate_file(file)
    if not is_valid:
        logger.error(f"File validation failed: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Process file
    processor = ExcelProcessor()
    results = processor.process_material_file(db, file, update_existing)
    
    logger.info(f"File processing completed: {results['rows_successful']} successful, {results['rows_failed']} failed")
    
    return results

@router.get("/template")
async def download_template():
    """
    Download Excel template for materials upload
    """
    logger.debug("Downloading materials template")
    
    processor = ExcelProcessor()
    template_bytes = processor.generate_material_template()
    
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    
    return StreamingResponse(
        BytesIO(template_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=material_template.xlsx"}
    )

# CLI endpoints
@router.get("/cli/list")
async def cli_list_products(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_owner_or_admin_user_dependency)
):
    """CLI endpoint to list products"""
    print("📦 CLI Product List")
    
    categories = db.query(models.Category).all()
    materials = db.query(models.Material).all()
    
    print(f"📋 Categories: {len(categories)}")
    for category in categories:
        print(f"  📍 {category.name}: {category.description or 'No description'}")
    
    print(f"\n📦 Materials: {len(materials)}")
    for material in materials[:10]:  # Show first 10
        category_name = db.query(models.Category).filter(
            models.Category.id == material.category_id
        ).first().name
        
        print(f"  📦 {material.name} ({category_name}): {material.unit or 'N/A'} - ₹{material.standard_cost}")
    
    if len(materials) > 10:
        print(f"  ... and {len(materials) - 10} more materials")
    
    return {
        "categories": len(categories),
        "materials": len(materials)
    }
