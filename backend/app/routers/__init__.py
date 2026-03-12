"""
API routers module
"""
# Add to any router file if these imports are missing
from app.auth import check_project_access
from app.auth import get_admin_user_dependency  # Add this function if missing
from app.routers import auth
from app.routers import users
from app.routers import products
from app.routers import projects
from app.routers import sites
from app.routers import po
from app.routers import stock
from app.routers import reports
from app.routers import uploads

# Export all routers
__all__ = [
    "auth",
    "users",
    "products",
    "projects",
    "sites",
    "po",
    "stock",
    "reports",
    "uploads"
]
