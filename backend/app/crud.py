"""
CRUD operations for the application
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
        """Delete record by ID"""
        logger.debug(f"Deleting {self.model.__name__} with ID: {id}")
        
        db_obj = db.query(self.model).filter(self.model.id == id).first()
        
        if db_obj:
            db.delete(db_obj)
            db.commit()
            logger.info(f"Deleted {self.model.__name__} with ID: {id}")
        
        return db_obj

# User CRUD
class CRUDUser(CRUDBase[models.User]):
    """CRUD operations for User model"""
    
    def get_by_email(self, db: Session, email: str) -> Optional[models.User]:
        """Get user by email"""
        logger.debug(f"Getting user by email: {email}")
        return db.query(models.User).filter(models.User.email == email).first()
    
    def get_by_username(self, db: Session, username: str) -> Optional[models.User]:
        """Get user by username"""
        logger.debug(f"Getting user by username: {username}")
        return db.query(models.User).filter(models.User.username == username).first()
    
    def create(self, db: Session, obj_in: schemas.UserCreate) -> models.User:
        """Create new user with hashed password"""
        logger.debug(f"Creating new user: {obj_in.username}")
        
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
        
        logger.info(f"Created user with ID: {db_obj.id}, username: {db_obj.username}")
        return db_obj
    
    def update(
        self, 
        db: Session, 
        db_obj: models.User, 
        obj_in: schemas.UserUpdate
    ) -> models.User:
        """Update user with optional password change"""
        logger.debug(f"Updating user: {db_obj.username}")
        
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
        
        logger.info(f"Updated user: {db_obj.username}")
        return db_obj
    
    def get_users_by_role(self, db: Session, role: schemas.UserRole) -> List[models.User]:
        """Get users by role"""
        logger.debug(f"Getting users by role: {role}")
        return db.query(models.User).filter(models.User.role == role).all()

# Category CRUD
class CRUDCategory(CRUDBase[models.Category]):
    """CRUD operations for Category model"""
    
    def get_by_name(self, db: Session, name: str) -> Optional[models.Category]:
        """Get category by name"""
        logger.debug(f"Getting category by name: {name}")
        return db.query(models.Category).filter(models.Category.name == name).first()
    
    def get_with_materials(self, db: Session, category_id: int) -> Optional[models.Category]:
        """Get category with its materials"""
        logger.debug(f"Getting category with materials: {category_id}")
        return db.query(models.Category).filter(
            models.Category.id == category_id
        ).first()

# Material CRUD
class CRUDMaterial(CRUDBase[models.Material]):
    """CRUD operations for Material model"""
    
    def get_by_name(self, db: Session, name: str) -> Optional[models.Material]:
        """Get material by name"""
        logger.debug(f"Getting material by name: {name}")
        return db.query(models.Material).filter(models.Material.name == name).first()
    
    def get_by_category(self, db: Session, category_id: int) -> List[models.Material]:
        """Get materials by category"""
        logger.debug(f"Getting materials by category: {category_id}")
        return db.query(models.Material).filter(
            models.Material.category_id == category_id
        ).all()
    
    def search(self, db: Session, search_term: str) -> List[models.Material]:
        """Search materials by name"""
        logger.debug(f"Searching materials for term: {search_term}")
        return db.query(models.Material).filter(
            models.Material.name.ilike(f"%{search_term}%")
        ).all()

# Project CRUD
class CRUDProject(CRUDBase[models.Project]):
    """CRUD operations for Project model"""
    
    def get_by_code(self, db: Session, code: str) -> Optional[models.Project]:
        """Get project by code"""
        logger.debug(f"Getting project by code: {code}")
        return db.query(models.Project).filter(models.Project.code == code).first()
    
    def create(self, db: Session, obj_in: schemas.ProjectCreate) -> models.Project:
        """Create project with user access"""
        logger.debug(f"Creating new project: {obj_in.name}")
        
        obj_in_data = obj_in.dict(exclude_unset=True)
        user_ids = obj_in_data.pop("user_ids", [])
        
        db_obj = models.Project(**obj_in_data)
        
        # Add users with access
        if user_ids:
            users = db.query(models.User).filter(models.User.id.in_(user_ids)).all()
            db_obj.users.extend(users)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        logger.info(f"Created project with ID: {db_obj.id}, code: {db_obj.code}")
        return db_obj
    
    def add_user_access(self, db: Session, project_id: int, user_id: int) -> bool:
        """Add user access to project"""
        logger.debug(f"Adding user {user_id} to project {project_id}")
        
        project = self.get(db, project_id)
        user = db.query(models.User).filter(models.User.id == user_id).first()
        
        if project and user and user not in project.users:
            project.users.append(user)
            db.commit()
            logger.info(f"Added user {user_id} to project {project_id}")
            return True
        
        logger.warning(f"Failed to add user {user_id} to project {project_id}")
        return False
    
    def remove_user_access(self, db: Session, project_id: int, user_id: int) -> bool:
        """Remove user access from project"""
        logger.debug(f"Removing user {user_id} from project {project_id}")
        
        project = self.get(db, project_id)
        user = db.query(models.User).filter(models.User.id == user_id).first()
        
        if project and user and user in project.users:
            project.users.remove(user)
            db.commit()
            logger.info(f"Removed user {user_id} from project {project_id}")
            return True
        
        logger.warning(f"Failed to remove user {user_id} from project {project_id}")
        return False

# Site CRUD
class CRUDSite(CRUDBase[models.Site]):
    """CRUD operations for Site model"""
    
    def get_by_project(self, db: Session, project_id: int) -> List[models.Site]:
        """Get sites by project"""
        logger.debug(f"Getting sites for project: {project_id}")
        return db.query(models.Site).filter(
            models.Site.project_id == project_id
        ).all()
    
    def get_active_sites(self, db: Session, project_id: int) -> List[models.Site]:
        """Get active sites by project"""
        logger.debug(f"Getting active sites for project: {project_id}")
        return db.query(models.Site).filter(
            and_(
                models.Site.project_id == project_id,
                models.Site.status == "active"
            )
        ).all()

# PO Entry CRUD
class CRUDPOEntry(CRUDBase[models.POEntry]):
    """CRUD operations for PO Entry model"""
    
    def get_by_project(self, db: Session, project_id: int) -> List[models.POEntry]:
        """Get PO entries by project"""
        logger.debug(f"Getting PO entries for project: {project_id}")
        return db.query(models.POEntry).filter(
            models.POEntry.project_id == project_id
        ).all()
    
    def get_by_supplier(self, db: Session, supplier_name: str) -> List[models.POEntry]:
        """Get PO entries by supplier"""
        logger.debug(f"Getting PO entries for supplier: {supplier_name}")
        return db.query(models.POEntry).filter(
            models.POEntry.supplier_name.ilike(f"%{supplier_name}%")
        ).all()
    
    def get_by_invoice(self, db: Session, invoice_no: str) -> Optional[models.POEntry]:
        """Get PO entry by invoice number"""
        logger.debug(f"Getting PO entry by invoice: {invoice_no}")
        return db.query(models.POEntry).filter(
            models.POEntry.invoice_no == invoice_no
        ).first()
    
    def get_total_cost_by_project(self, db: Session, project_id: int) -> Decimal:
        """Get total PO cost for a project"""
        logger.debug(f"Calculating total PO cost for project: {project_id}")
        
        result = db.query(func.sum(models.POEntry.total_cost)).filter(
            models.POEntry.project_id == project_id
        ).scalar()
        
        return result or Decimal('0.00')

# Stock Entry CRUD
class CRUDStockEntry(CRUDBase[models.StockEntry]):
    """CRUD operations for Stock Entry model"""
    
    def get_by_site(self, db: Session, site_id: int) -> List[models.StockEntry]:
        """Get stock entries by site"""
        logger.debug(f"Getting stock entries for site: {site_id}")
        return db.query(models.StockEntry).filter(
            models.StockEntry.site_id == site_id
        ).all()
    
    def get_by_site_and_material(
        self, 
        db: Session, 
        site_id: int, 
        material_id: int
    ) -> List[models.StockEntry]:
        """Get stock entries by site and material"""
        logger.debug(f"Getting stock entries for site {site_id}, material {material_id}")
        return db.query(models.StockEntry).filter(
            and_(
                models.StockEntry.site_id == site_id,
                models.StockEntry.material_id == material_id
            )
        ).order_by(models.StockEntry.entry_date).all()
    
    def get_by_date_range(
        self, 
        db: Session, 
        site_id: int, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[models.StockEntry]:
        """Get stock entries by date range"""
        logger.debug(f"Getting stock entries for site {site_id} from {start_date} to {end_date}")
        return db.query(models.StockEntry).filter(
            and_(
                models.StockEntry.site_id == site_id,
                models.StockEntry.entry_date >= start_date,
                models.StockEntry.entry_date <= end_date
            )
        ).order_by(models.StockEntry.entry_date).all()

# Daily Stock Report CRUD
class CRUDDailyStockReport(CRUDBase[models.DailyStockReport]):
    """CRUD operations for Daily Stock Report model"""
    
    def get_by_site_and_date(
        self, 
        db: Session, 
        site_id: int, 
        report_date: date
    ) -> List[models.DailyStockReport]:
        """Get daily report for site on specific date"""
        logger.debug(f"Getting daily report for site {site_id} on {report_date}")
        
        start_of_day = datetime.combine(report_date, datetime.min.time())
        end_of_day = datetime.combine(report_date, datetime.max.time())
        
        return db.query(models.DailyStockReport).filter(
            and_(
                models.DailyStockReport.site_id == site_id,
                models.DailyStockReport.report_date >= start_of_day,
                models.DailyStockReport.report_date <= end_of_day
            )
        ).all()
    
    def get_latest_report(
        self, 
        db: Session, 
        site_id: int, 
        material_id: int
    ) -> Optional[models.DailyStockReport]:
        """Get latest daily report for site and material"""
        logger.debug(f"Getting latest report for site {site_id}, material {material_id}")
        
        return db.query(models.DailyStockReport).filter(
            and_(
                models.DailyStockReport.site_id == site_id,
                models.DailyStockReport.material_id == material_id
            )
        ).order_by(desc(models.DailyStockReport.report_date)).first()
    
    def generate_daily_reports(self, db: Session, site_id: int, report_date: date):
        """Generate daily reports for all materials at a site"""
        logger.info(f"Generating daily reports for site {site_id} on {report_date}")
        
        # This would be implemented with the stock calculation logic
        # For now, it's a placeholder
        pass

# Audit Log CRUD
class CRUDAuditLog(CRUDBase[models.AuditLog]):
    """CRUD operations for Audit Log model"""
    
    def get_by_user(self, db: Session, user_id: int) -> List[models.AuditLog]:
        """Get audit logs by user"""
        logger.debug(f"Getting audit logs for user: {user_id}")
        return db.query(models.AuditLog).filter(
            models.AuditLog.user_id == user_id
        ).order_by(desc(models.AuditLog.created_at)).all()
    
    def get_by_action(self, db: Session, action: str) -> List[models.AuditLog]:
        """Get audit logs by action"""
        logger.debug(f"Getting audit logs for action: {action}")
        return db.query(models.AuditLog).filter(
            models.AuditLog.action == action
        ).order_by(desc(models.AuditLog.created_at)).all()
    
    def log_action(
        self,
        db: Session,
        user_id: int,
        action: str,
        table_name: str,
        record_id: Optional[int] = None,
        old_values: Optional[str] = None,
        new_values: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> models.AuditLog:
        """Log an action to audit trail"""
        logger.debug(f"Logging audit action: {action} by user {user_id}")
        
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
        
        logger.info(f"Audit log created for action: {action}")
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

# CLI helper functions
def cli_list_users(db: Session):
    """List all users in CLI"""
    print("👥 Listing all users:")
    users = db.query(models.User).all()
    
    for user in users:
        status = "✅" if user.is_active else "❌"
        print(f"  {status} {user.username} ({user.email}) - Role: {user.role.value}")
    
    print(f"\nTotal users: {len(users)}")

def cli_list_projects(db: Session):
    """List all projects in CLI"""
    print("🏗️  Listing all projects:")
    projects = db.query(models.Project).all()
    
    for project in projects:
        print(f"  📋 {project.code}: {project.name} - Status: {project.status}")
        if project.sites:
            print(f"    Sites: {len(project.sites)}")
    
    print(f"\nTotal projects: {len(projects)}")

def cli_show_stats(db: Session):
    """Show database statistics"""
    print("📊 Database Statistics:")
    
    user_count = db.query(func.count(models.User.id)).scalar()
    project_count = db.query(func.count(models.Project.id)).scalar()
    site_count = db.query(func.count(models.Site.id)).scalar()
    material_count = db.query(func.count(models.Material.id)).scalar()
    po_count = db.query(func.count(models.POEntry.id)).scalar()
    stock_count = db.query(func.count(models.StockEntry.id)).scalar()
    
    print(f"  👥 Users: {user_count}")
    print(f"  🏗️  Projects: {project_count}")
    print(f"  🏢 Sites: {site_count}")
    print(f"  📦 Materials: {material_count}")
    print(f"  📝 PO Entries: {po_count}")
    print(f"  📊 Stock Entries: {stock_count}")
