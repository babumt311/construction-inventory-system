"""
SQLAlchemy models for the application
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    ForeignKey, Text, Numeric, Enum, Table, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.database import Base
import logging

logger = logging.getLogger(__name__)

class UserRole(str, enum.Enum):
    """User roles enumeration"""
    ADMIN = "admin"
    OWNER = "owner"
    USER = "user"

# Association table for user-project access
user_project_access = Table(
    'user_project_access',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
)

class User(Base):
    """User model with role-based access control"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(200))
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    projects = relationship("Project", secondary=user_project_access, back_populates="users")
    logs = relationship("AuditLog", back_populates="user")
    po_entries = relationship("POEntry", back_populates="user")
    stock_entries = relationship("StockEntry", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"

class Category(Base):
    """Material category model"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    materials = relationship("Material", back_populates="category", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Category(id={self.id}, name={self.name})>"

class Material(Base):
    """Material/Product model"""
    __tablename__ = "materials"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    unit = Column(String(50))  # kg, pieces, liters, etc.
    description = Column(Text)
    standard_cost = Column(Numeric(10, 2), default=0.00)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    category = relationship("Category", back_populates="materials")
    po_entries = relationship("POEntry", back_populates="material")
    stock_entries = relationship("StockEntry", back_populates="material")
    daily_reports = relationship("DailyStockReport", back_populates="material")
    
    # Indexes
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )
    
    def __repr__(self):
        return f"<Material(id={self.id}, name={self.name}, category_id={self.category_id})>"

class Project(Base):
    """Project model"""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    code = Column(String(50), unique=True, index=True)
    
    client = Column(String(200))
    budget = Column(Numeric(15, 2), default=0.00)
    
    description = Column(Text)
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    status = Column(String(50), default="active")  # active, completed, on-hold
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    users = relationship("User", secondary=user_project_access, back_populates="projects")
    sites = relationship("Site", back_populates="project", cascade="all, delete-orphan")
    po_entries = relationship("POEntry", back_populates="project")
    
    # --- NEW RELATIONSHIPS ADDED HERE ---
    team_members = relationship("ProjectTeamMember", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name}, code={self.code})>"

# --- NEW MODEL: TEAM MEMBERS ---
class ProjectTeamMember(Base):
    """Project Team Member model"""
    __tablename__ = "project_team_members"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)
    status = Column(String(50), default="Active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="team_members")

    def __repr__(self):
        return f"<ProjectTeamMember(id={self.id}, name={self.name}, role={self.role})>"

# --- NEW MODEL: TASKS ---
class Task(Base):
    """Project Task model"""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    priority = Column(String(50), default="Medium")
    estimated_hours = Column(Float, default=0.0)
    due_date = Column(DateTime(timezone=True))
    status = Column(String(50), default="TO DO")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="tasks")

    def __repr__(self):
        return f"<Task(id={self.id}, title={self.title}, status={self.status})>"

class Site(Base):
    """Site/Sub-project model"""
    __tablename__ = "sites"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    code = Column(String(50), index=True)
    location = Column(String(500))
    manager = Column(String(200))
    status = Column(String(50), default="active")  # active, completed, closed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="sites")
    stock_entries = relationship("StockEntry", back_populates="site")
    daily_reports = relationship("DailyStockReport", back_populates="site")
    
    def __repr__(self):
        return f"<Site(id={self.id}, name={self.name}, project_id={self.project_id})>"

class POEntry(Base):
    """Purchase Order Entry model"""
    __tablename__ = "po_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    supplier_name = Column(String(200), nullable=False)
    invoice_no = Column(String(100), nullable=False, index=True)
    quantity = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_cost = Column(Numeric(10, 2), nullable=False)
    po_date = Column(DateTime(timezone=True), server_default=func.now())
    delivery_date = Column(DateTime(timezone=True))
    remarks = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="po_entries")
    material = relationship("Material", back_populates="po_entries")
    user = relationship("User", back_populates="po_entries")
    
    def __repr__(self):
        return f"<POEntry(id={self.id}, invoice_no={self.invoice_no}, supplier={self.supplier_name})>"

class StockEntry(Base):
    """Stock Entry model"""
    __tablename__ = "stock_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    entry_type = Column(String(50), nullable=False)  # received, used, returned_received, returned_supplier
    quantity = Column(Numeric(10, 2), nullable=False)
    supplier_name = Column(String(200))
    invoice_no = Column(String(100))
    reference = Column(String(200))  # Reference to PO or other document
    remarks = Column(Text)
    entry_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    site = relationship("Site", back_populates="stock_entries")
    material = relationship("Material", back_populates="stock_entries")
    user = relationship("User", back_populates="stock_entries")
    
    def __repr__(self):
        return f"<StockEntry(id={self.id}, site_id={self.site_id}, type={self.entry_type}, qty={self.quantity})>"

class DailyStockReport(Base):
    """Daily Stock Report model for each site"""
    __tablename__ = "daily_stock_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    report_date = Column(DateTime(timezone=True), nullable=False, index=True)
    opening_stock = Column(Numeric(10, 2), default=0.00)
    received = Column(Numeric(10, 2), default=0.00)
    used = Column(Numeric(10, 2), default=0.00)
    returned_received = Column(Numeric(10, 2), default=0.00)  # rr
    returned_supplier = Column(Numeric(10, 2), default=0.00)  # rs
    closing_stock = Column(Numeric(10, 2), default=0.00)
    total_received = Column(Numeric(10, 2), default=0.00)  # TR
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    site = relationship("Site", back_populates="daily_reports")
    material = relationship("Material", back_populates="daily_reports")
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('site_id', 'material_id', 'report_date', name='unique_daily_report'),
    )
    
    def __repr__(self):
        return f"<DailyStockReport(site={self.site_id}, material={self.material_id}, date={self.report_date})>"

class AuditLog(Base):
    """Audit Log model for tracking user activities"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)  # CREATE, UPDATE, DELETE, LOGIN, etc.
    table_name = Column(String(100), nullable=False)
    record_id = Column(Integer, nullable=True)
    old_values = Column(Text)  # JSON string of old values
    new_values = Column(Text)  # JSON string of new values
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, user={self.user_id}, action={self.action})>"

# Additional models for report caching
class ReportCache(Base):
    """Report caching model"""
    __tablename__ = "report_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String(100), nullable=False, index=True)
    parameters = Column(Text)  # JSON string of report parameters
    data = Column(Text)  # JSON string of report data
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    
    def __repr__(self):
        return f"<ReportCache(id={self.id}, type={self.report_type})>"

# CLI Output helper
def log_model_creation():
    """Log model creation for debugging"""
    logger.info("Database models initialized successfully")
    logger.info(f"Tables created: {Base.metadata.tables.keys()}")
