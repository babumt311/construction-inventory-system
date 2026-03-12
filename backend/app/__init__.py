"""
Construction Inventory System Backend Application
"""

__version__ = "1.0.0"
__author__ = "Construction Inventory Team"
__description__ = "Backend API for Construction Site Material Inventory Management System"

# Import main components
from app.main import app
from app.config import settings
from app.database import Base, engine, SessionLocal

# Initialize database tables
def init_database():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)

# CLI export
__all__ = ["app", "settings", "Base", "engine", "SessionLocal", "init_database"]
