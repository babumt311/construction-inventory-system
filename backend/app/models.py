"""
SQLAlchemy models for the application - ENTERPRISE IMMUTABLE LEDGER
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    ForeignKey, Text, Numeric, Enum, Table, UniqueConstraint, Date
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.database import Base
import logging

logger = logging.getLogger(__name__)

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OWNER = "owner"
    USER = "user"

user_project_access = Table(
    'user_project_access',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(200))
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True) # Soft delete flag
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    projects = relationship("Project", secondary=user_project_access, back_populates="users")
    logs = relationship("AuditLog", back_populates="user")
    po_entries = relationship("POEntry", back_populates="user")
    stock_entries = relationship("StockEntry", back_populates="user")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True) # Soft delete flag
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    materials = relationship("Material", back_populates="category")

class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    unit = Column(String(50))
    description = Column(Text)
    standard_cost = Column(Numeric(10, 2), default=0.00)
    is_active = Column(Boolean, default=True) # Soft delete flag
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    category = relationship("Category", back_populates="materials")
    po_entries = relationship("POEntry", back_populates="material")
    stock_entries = relationship("StockEntry", back_populates="material")
    daily_reports = relationship("DailyStockReport", back_populates="material")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    code = Column(String(50), unique=True, index=True)
    client = Column(String(200))
    budget = Column(Numeric(15, 2), default=0.00)
    description = Column(Text)
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    status = Column(String(50), default="active")
    is_active = Column(Boolean, default=True) # Soft delete flag
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    users = relationship("User", secondary=user_project_access, back_populates="projects")
    sites = relationship("Site", back_populates="project")
    po_entries = relationship("POEntry", back_populates="project")
    team_members = relationship("ProjectTeamMember", back_populates="project")
    tasks = relationship("Task", back_populates="project")

class ProjectTeamMember(Base):
    __tablename__ = "project_team_members"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)
    status = Column(String(50), default="Active")
    is_active = Column(Boolean, default=True) # Soft delete flag
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    project = relationship("Project", back_populates="team_members")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    priority = Column(String(50), default="Medium")
    estimated_hours = Column(Float, default=0.0)
    due_date = Column(DateTime(timezone=True))
    status = Column(String(50), default="TO DO")
    is_active = Column(Boolean, default=True) # Soft delete flag
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    project = relationship("Project", back_populates="tasks")

class Site(Base):
    __tablename__ = "sites"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    code = Column(String(50), index=True)
    location = Column(String(500))
    manager = Column(String(200))
    status = Column(String(50), default="active")
    is_active = Column(Boolean, default=True) # Soft delete flag
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    project = relationship("Project", back_populates="sites")
    stock_entries = relationship("StockEntry", back_populates="site")
    daily_reports = relationship("DailyStockReport", back_populates="site")

class POEntry(Base):
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
    
    project = relationship("Project", back_populates="po_entries")
    material = relationship("Material", back_populates="po_entries")
    user = relationship("User", back_populates="po_entries")

class StockEntry(Base):
    __tablename__ = "stock_entries"
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    entry_type = Column(String(50), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    
    # --- SNAPSHOT DATA LOCKED IN AT TIME OF TRANSACTION ---
    unit_cost = Column(Numeric(10, 2), default=0.00) 
    tax_percent = Column(Numeric(5, 2), default=0.00)
    tax_amount = Column(Numeric(10, 2), default=0.00)
    total_cost = Column(Numeric(10, 2), default=0.00)
    # ------------------------------------------------------
    
    supplier_name = Column(String(200))
    invoice_no = Column(String(100))
    invoice_date = Column(Date, nullable=True)
    reference = Column(String(200))
    remarks = Column(Text)
    entry_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    site = relationship("Site", back_populates="stock_entries")
    material = relationship("Material", back_populates="stock_entries")
    user = relationship("User", back_populates="stock_entries")

class DailyStockReport(Base):
    __tablename__ = "daily_stock_reports"
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    report_date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # --- PHYSICAL QUANTITIES ---
    opening_stock = Column(Numeric(10, 2), default=0.00)
    received = Column(Numeric(10, 2), default=0.00)
    used = Column(Numeric(10, 2), default=0.00)
    returned_received = Column(Numeric(10, 2), default=0.00)
    returned_supplier = Column(Numeric(10, 2), default=0.00)
    closing_stock = Column(Numeric(10, 2), default=0.00)
    total_received = Column(Numeric(10, 2), default=0.00)
    
    # --- LOCKED FINANCIAL SNAPSHOTS ---
    received_value = Column(Numeric(10, 2), default=0.00)
    used_value = Column(Numeric(10, 2), default=0.00)
    # ----------------------------------
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    site = relationship("Site", back_populates="daily_reports")
    material = relationship("Material", back_populates="daily_reports")
    
    __table_args__ = (UniqueConstraint('site_id', 'material_id', 'report_date', name='unique_daily_report'),)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)
    table_name = Column(String(100), nullable=False)
    record_id = Column(Integer, nullable=True)
    old_values = Column(Text)
    new_values = Column(Text)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="logs")

class ReportCache(Base):
    __tablename__ = "report_cache"
    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String(100), nullable=False, index=True)
    parameters = Column(Text)
    data = Column(Text)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))

def log_model_creation():
    logger.info("Database models initialized successfully (Enterprise Immutable Ledger)")
