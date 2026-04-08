"""
CRUD operations for the application - Enterprise Soft Delete Edition
"""
from typing import Optional, List, Dict, Any, Type, TypeVar, Generic
from sqlalchemy.orm import Session, Query
from sqlalchemy import and_, or_, func, desc, asc
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging
from app import models, schemas

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=models.Base)

class CRUDBase(Generic[ModelType]):
    """Base class for CRUD operations"""
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    def get(self, db: Session, id: int) -> Optional[ModelType]:
        """Get single record by ID"""
        logger.debug(f"Getting {self.model.__name__} with ID: {id}")
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """Get multiple records with optional filtering"""
        logger.debug(f"Getting multiple {self.model.__name__} records")
        
        query = db.query(self.model)
        
        # Enterprise Protocol: Automatically hide soft-deleted records if the model supports it
        if hasattr(self.model, "is_active"):
            query = query.filter(self.model.is_active == True)
            
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if isinstance(value, list):
                        query = query.filter(getattr(self.model, field).in_(value))
                    else:
                        query = query.filter(getattr(self.model, field) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def create(self, db: Session, obj_in: schemas.BaseModel) -> ModelType:
        """Create new record"""
        logger.debug(f"Creating new {self.model.__name__}")
        
        obj_in_data = obj_in.dict(exclude_unset=True)
        db_obj = self.model(**obj_in_data)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        logger.info(f"Created {self.model.__name__} with ID: {db_obj.id}")
        return db_obj
    
    def update(
        self, 
        db: Session, 
        db_obj: ModelType, 
        obj_in: schemas.BaseModel
    ) -> ModelType:
        """Update existing record"""
        logger.debug(f"Updating {self.model.__name__} with ID: {db_obj.id}")
        
        update_data = obj_in.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        logger.info(f"Updated {self.model.__name__} with ID: {db_obj.id}")
        return db_obj
    
    def delete(self, db: Session, id: int) -> Optional[ModelType]:
        """Delete record by ID - Uses Soft Delete if supported"""
        logger.debug(f"Deleting {self.model.__name__} with ID: {id}")
        
        db_obj = db.query(self.model).filter(self.model.id == id).first()
        
        if db_obj:
            if hasattr(db_obj, "is_active"):
                db_obj.is_active = False  # Enterprise Soft Delete
                db.add(db_obj)
            else:
                db.delete(db_obj)         # Hard Delete for transactional tables
            db.commit()
            logger.info(f"Deleted {self.model.__name__} with ID: {id}")
        
        return db_obj

# User CRUD
class CRUDUser(CRUDBase[models.User]):
    def get_by_email(self, db: Session, email: str) -> Optional[models.User]:
        return db.query(models.User).filter(models.User.email == email, models.User.is_active == True).first()
    
    def get_by_username(self, db: Session, username: str) -> Optional[models.User]:
        return db.query(models.User).filter(models.User.username == username, models.User.is_active == True).first()
    
    def create(self, db: Session, obj_in: schemas.UserCreate) -> models.User:
        obj_in_data = obj_in.dict(exclude_unset=True)
        password = obj_in_data.pop("password")
        
        from app.auth import get_password_hash
        hashed_password = get_password_hash(password)
        
        db_obj = models.User(
            **obj_in_data,
            hashed_password=hashed_password
        )
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(self, db: Session, db_obj: models.User, obj_in: schemas.UserUpdate) -> models.User:
        update_data = obj_in.dict(exclude_unset=True)
        
        if "password" in update_data:
            from app.auth import get_password_hash
            hashed_password = get_password_hash(update_data.pop("password"))
            update_data["hashed_password"] = hashed_password
        
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_users_by_role(self, db: Session, role: schemas.UserRole) -> List[models.User]:
        return db.query(models.User).filter(models.User.role == role, models.User.is_active == True).all()

# Category CRUD
class CRUDCategory(CRUDBase[models.Category]):
    def get_by_name(self, db: Session, name: str) -> Optional[models.Category]:
        return db.query(models.Category).filter(models.Category.name == name, models.Category.is_active == True).first()
    
    def get_with_materials(self, db: Session, category_id: int) -> Optional[models.Category]:
        return db.query(models.Category).filter(models.Category.id == category_id, models.Category.is_active == True).first()

# Material CRUD
class CRUDMaterial(CRUDBase[models.Material]):
    def get_by_name(self, db: Session, name: str) -> Optional[models.Material]:
        return db.query(models.Material).filter(models.Material.name == name, models.Material.is_active == True).first()
    
    def get_by_category(self, db: Session, category_id: int) -> List[models.Material]:
        return db.query(models.Material).filter(
            models.Material.category_id == category_id,
            models.Material.is_active == True
        ).all()
    
    def search(self, db: Session, search_term: str) -> List[models.Material]:
        return db.query(models.Material).filter(
            models.Material.name.ilike(f"%{search_term}%"),
            models.Material.is_active == True
        ).all()

# Project CRUD
class CRUDProject(CRUDBase[models.Project]):
    def get_by_code(self, db: Session, code: str) -> Optional[models.Project]:
        return db.query(models.Project).filter(models.Project.code == code, models.Project.is_active == True).first()
    
    def create(self, db: Session, obj_in: schemas.ProjectCreate) -> models.Project:
        obj_in_data = obj_in.dict(exclude_unset=True)
        user_ids = obj_in_data.pop("user_ids", [])
        
        db_obj = models.Project(**obj_in_data)
        
        if user_ids:
            users = db.query(models.User).filter(models.User.id.in_(user_ids)).all()
            db_obj.users.extend(users)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def add_user_access(self, db: Session, project_id: int, user_id: int) -> bool:
        project = self.get(db, project_id)
        user = db.query(models.User).filter(models.User.id == user_id).first()
        
        if project and user and user not in project.users:
            project.users.append(user)
            db.commit()
            return True
        return False
    
    def remove_user_access(self, db: Session, project_id: int, user_id: int) -> bool:
        project = self.get(db, project_id)
        user = db.query(models.User).filter(models.User.id == user_id).first()
        
        if project and user and user in project.users:
            project.users.remove(user)
            db.commit()
            return True
        return False

# Site CRUD
class CRUDSite(CRUDBase[models.Site]):
    def get_by_project(self, db: Session, project_id: int) -> List[models.Site]:
        return db.query(models.Site).filter(
            models.Site.project_id == project_id,
            models.Site.is_active == True
        ).all()
    
    def get_active_sites(self, db: Session, project_id: int) -> List[models.Site]:
        return db.query(models.Site).filter(
            and_(
                models.Site.project_id == project_id,
                models.Site.status == "active",
                models.Site.is_active == True
            )
        ).all()

# PO Entry CRUD
class CRUDPOEntry(CRUDBase[models.POEntry]):
    def get_by_project(self, db: Session, project_id: int) -> List[models.POEntry]:
        return db.query(models.POEntry).filter(models.POEntry.project_id == project_id).all()
    
    def get_by_supplier(self, db: Session, supplier_name: str) -> List[models.POEntry]:
        return db.query(models.POEntry).filter(models.POEntry.supplier_name.ilike(f"%{supplier_name}%")).all()
    
    def get_by_invoice(self, db: Session, invoice_no: str) -> Optional[models.POEntry]:
        return db.query(models.POEntry).filter(models.POEntry.invoice_no == invoice_no).first()
    
    def get_total_cost_by_project(self, db: Session, project_id: int) -> Decimal:
        result = db.query(func.sum(models.POEntry.total_cost)).filter(
            models.POEntry.project_id == project_id
        ).scalar()
        return result or Decimal('0.00')

# Stock Entry CRUD
class CRUDStockEntry(CRUDBase[models.StockEntry]):
    def get_by_site(self, db: Session, site_id: int) -> List[models.StockEntry]:
        return db.query(models.StockEntry).filter(models.StockEntry.site_id == site_id).all()
    
    def get_by_site_and_material(self, db: Session, site_id: int, material_id: int) -> List[models.StockEntry]:
        return db.query(models.StockEntry).filter(
            and_(
                models.StockEntry.site_id == site_id,
                models.StockEntry.material_id == material_id
            )
        ).order_by(models.StockEntry.entry_date).all()
    
    def get_by_date_range(self, db: Session, site_id: int, start_date: datetime, end_date: datetime) -> List[models.StockEntry]:
        return db.query(models.StockEntry).filter(
            and_(
                models.StockEntry.site_id == site_id,
                models.StockEntry.entry_date >= start_date,
                models.StockEntry.entry_date <= end_date
            )
        ).order_by(models.StockEntry.entry_date).all()

# Daily Stock Report CRUD
class CRUDDailyStockReport(CRUDBase[models.DailyStockReport]):
    def get_by_site_and_date(self, db: Session, site_id: int, report_date: date) -> List[models.DailyStockReport]:
        start_of_day = datetime.combine(report_date, datetime.min.time())
        end_of_day = datetime.combine(report_date, datetime.max.time())
        
        return db.query(models.DailyStockReport).filter(
            and_(
                models.DailyStockReport.site_id == site_id,
                models.DailyStockReport.report_date >= start_of_day,
                models.DailyStockReport.report_date <= end_of_day
            )
        ).all()
    
    def get_latest_report(self, db: Session, site_id: int, material_id: int) -> Optional[models.DailyStockReport]:
        return db.query(models.DailyStockReport).filter(
            and_(
                models.DailyStockReport.site_id == site_id,
                models.DailyStockReport.material_id == material_id
            )
        ).order_by(desc(models.DailyStockReport.report_date)).first()

# Audit Log CRUD
class CRUDAuditLog(CRUDBase[models.AuditLog]):
    def get_by_user(self, db: Session, user_id: int) -> List[models.AuditLog]:
        return db.query(models.AuditLog).filter(models.AuditLog.user_id == user_id).order_by(desc(models.AuditLog.created_at)).all()
    
    def get_by_action(self, db: Session, action: str) -> List[models.AuditLog]:
        return db.query(models.AuditLog).filter(models.AuditLog.action == action).order_by(desc(models.AuditLog.created_at)).all()
    
    def log_action(self, db: Session, user_id: int, action: str, table_name: str, record_id: Optional[int] = None, old_values: Optional[str] = None, new_values: Optional[str] = None, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> models.AuditLog:
        audit_log = models.AuditLog(
            user_id=user_id,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log

# Instantiate CRUD classes
crud_user = CRUDUser(models.User)
crud_category = CRUDCategory(models.Category)
crud_material = CRUDMaterial(models.Material)
crud_project = CRUDProject(models.Project)
crud_site = CRUDSite(models.Site)
crud_po_entry = CRUDPOEntry(models.POEntry)
crud_stock_entry = CRUDStockEntry(models.StockEntry)
crud_daily_report = CRUDDailyStockReport(models.DailyStockReport)
crud_audit_log = CRUDAuditLog(models.AuditLog)
