"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# User schemas
class UserRole(str, Enum):
    ADMIN = "admin"
    OWNER = "owner"
    USER = "user"

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)

class UserInDB(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserWithProjects(UserInDB):
    projects: List["ProjectBase"] = []

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInDB

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[UserRole] = None

# Category schemas
class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None

class CategoryInDB(CategoryBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Material schemas
class MaterialBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    category_id: int
    unit: Optional[str] = None
    description: Optional[str] = None
    standard_cost: Optional[Decimal] = Field(0.00, ge=0)

class MaterialCreate(MaterialBase):
    pass

class MaterialUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    category_id: Optional[int] = None
    unit: Optional[str] = None
    description: Optional[str] = None
    standard_cost: Optional[Decimal] = Field(None, ge=0)

class MaterialInDB(MaterialBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    category: Optional[CategoryInDB] = None
    
    class Config:
        from_attributes = True

# Project schemas
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    code: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str = "active"

class ProjectCreate(ProjectBase):
    user_ids: Optional[List[int]] = []  # Users with access to this project

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    code: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None

class ProjectInDB(ProjectBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    users: List[UserInDB] = []
    
    class Config:
        from_attributes = True

# Site schemas
class SiteBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    project_id: int
    code: Optional[str] = None
    location: Optional[str] = None
    manager: Optional[str] = None
    status: str = "active"

class SiteCreate(SiteBase):
    pass

class SiteUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    code: Optional[str] = None
    location: Optional[str] = None
    manager: Optional[str] = None
    status: Optional[str] = None

class SiteInDB(SiteBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    project: Optional[ProjectInDB] = None
    
    class Config:
        from_attributes = True

# PO Entry schemas
class POEntryBase(BaseModel):
    project_id: int
    material_id: int
    supplier_name: str = Field(..., min_length=2, max_length=200)
    invoice_no: str = Field(..., min_length=2, max_length=100)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    total_cost: Decimal = Field(..., ge=0)
    po_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    remarks: Optional[str] = None

    @validator('total_cost')
    def validate_total_cost(cls, v, values):
        if 'quantity' in values and 'unit_price' in values:
            expected = values['quantity'] * values['unit_price']
            if v != expected:
                logger.warning(f"Total cost validation: provided={v}, expected={expected}")
        return v

class POEntryCreate(POEntryBase):
    pass

class POEntryUpdate(BaseModel):
    supplier_name: Optional[str] = Field(None, min_length=2, max_length=200)
    invoice_no: Optional[str] = Field(None, min_length=2, max_length=100)
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    total_cost: Optional[Decimal] = Field(None, ge=0)
    po_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    remarks: Optional[str] = None

class POEntryInDB(POEntryBase):
    id: int
    created_by: int
    created_at: datetime
    project: Optional[ProjectInDB] = None
    material: Optional[MaterialInDB] = None
    user: Optional[UserInDB] = None
    
    class Config:
        from_attributes = True

# Stock Entry schemas
class StockEntryType(str, Enum):
    RECEIVED = "received"
    USED = "used"
    RETURNED_RECEIVED = "returned_received"  # rr
    RETURNED_SUPPLIER = "returned_supplier"  # rs

class StockEntryBase(BaseModel):
    site_id: int
    material_id: int
    entry_type: StockEntryType
    quantity: Decimal
    supplier_name: Optional[str] = None
    invoice_no: Optional[str] = None
    reference: Optional[str] = None
    remarks: Optional[str] = None
    entry_date: Optional[datetime] = None

class StockEntryCreate(StockEntryBase):
    pass

class StockEntryUpdate(BaseModel):
    quantity: Optional[Decimal] = None
    supplier_name: Optional[str] = None
    invoice_no: Optional[str] = None
    reference: Optional[str] = None
    remarks: Optional[str] = None
    entry_date: Optional[datetime] = None

class StockEntryInDB(StockEntryBase):
    id: int
    created_by: int
    created_at: datetime
    site: Optional[SiteInDB] = None
    material: Optional[MaterialInDB] = None
    user: Optional[UserInDB] = None
    
    class Config:
        from_attributes = True

# Daily Stock Report schemas
class DailyStockReportBase(BaseModel):
    site_id: int
    material_id: int
    report_date: datetime
    opening_stock: Decimal = Field(0.00, ge=0)
    received: Decimal = Field(0.00, ge=0)
    used: Decimal = Field(0.00, ge=0)
    returned_received: Decimal = Field(0.00, ge=0)
    returned_supplier: Decimal = Field(0.00, ge=0)
    closing_stock: Decimal = Field(0.00)
    total_received: Decimal = Field(0.00, ge=0)

class DailyStockReportCreate(DailyStockReportBase):
    pass

class DailyStockReportInDB(DailyStockReportBase):
    id: int
    created_at: datetime
    site: Optional[SiteInDB] = None
    material: Optional[MaterialInDB] = None
    
    class Config:
        from_attributes = True

# Report schemas
class ReportFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    project_id: Optional[int] = None
    site_id: Optional[int] = None
    material_id: Optional[int] = None
    supplier_name: Optional[str] = None
    category_id: Optional[int] = None

class MaterialWiseReport(BaseModel):
    category: str
    material: str
    quantity: Decimal
    unit: str
    unit_cost: Decimal
    total_cost: Decimal

class SupplierWiseReport(BaseModel):
    supplier_name: str
    material: str
    quantity: Decimal
    unit: str
    total_cost: Decimal
    invoice_no: str
    purchase_date: datetime

class PeriodReport(BaseModel):
    material: str
    unit: str
    opening_stock: Decimal
    received: Decimal
    total_issued: Decimal
    returned: Decimal
    closing_stock: Decimal
    remarks: Optional[str] = None

# Audit Log schemas
class AuditLogBase(BaseModel):
    user_id: int
    action: str
    table_name: str
    record_id: Optional[int] = None
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AuditLogCreate(AuditLogBase):
    pass

class AuditLogInDB(AuditLogBase):
    id: int
    created_at: datetime
    user: Optional[UserInDB] = None
    
    class Config:
        from_attributes = True

# Excel Upload schemas
class ExcelUploadResponse(BaseModel):
    message: str
    rows_processed: int
    rows_successful: int
    rows_failed: int
    errors: Optional[List[str]] = None

# Stock Calculation schemas
class StockCalculationRequest(BaseModel):
    site_id: int
    material_id: int
    date: datetime

class StockBalance(BaseModel):
    material_id: int
    material_name: str
    current_balance: Decimal
    opening_balance: Decimal
    total_received: Decimal
    total_used: Decimal
    total_returned_received: Decimal
    total_returned_supplier: Decimal

# Response wrappers
class PaginatedResponse(BaseModel):
    data: List[Any]
    total: int
    page: int
    size: int
    pages: int

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None

# Update forward references
UserWithProjects.update_forward_refs()
ProjectInDB.update_forward_refs()

# CLI Output helper
def log_schema_validation(data: dict, schema_name: str):
    """Log schema validation for debugging"""
    logger.debug(f"Validating data against {schema_name} schema")
    logger.debug(f"Data: {data}")
