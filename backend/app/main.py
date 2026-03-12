"""
Main FastAPI application
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging
from typing import List
import uvicorn
from contextlib import asynccontextmanager

# Import application components
from app.config import settings
from app.database import engine, Base, get_db, test_database_connection
from app.models import log_model_creation
from app.auth import create_admin_user
from app import crud
from app.routers import (
    auth, users, products, projects, sites, po, stock, 
    reports, uploads
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("🚀 Starting Construction Inventory System Backend")
    logger.info(f"📝 Application: {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"🔧 Debug Mode: {settings.DEBUG}")
    
    # Test database connection
    if test_database_connection():
        logger.info("✅ Database connection successful")
        
        # Create database tables
        logger.info("🗄️ Creating database tables...")
        Base.metadata.create_all(bind=engine)
        log_model_creation()
        
        # Create default admin user
        with Session(engine) as db:
            create_admin_user(db)
            logger.info("👑 Default admin user checked/created")
    else:
        logger.error("❌ Database connection failed")
    
    logger.info("✅ Startup complete")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("🛑 Shutting down application")
    logger.info("👋 Goodbye!")

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for Construction Site Material Inventory Management System",
    lifespan=lifespan,
    debug=settings.DEBUG,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(sites.router, prefix="/api")
app.include_router(po.router, prefix="/api")
app.include_router(stock.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")

# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint - API information
    """
    logger.debug("Root endpoint accessed")
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Construction Site Material Inventory Management System",
        "docs": "/api/docs" if settings.DEBUG else None,
        "endpoints": [
            "/api/auth/* - Authentication",
            "/api/users/* - User Management",
            "/api/products/* - Material Management",
            "/api/projects/* - Project Management",
            "/api/sites/* - Site Management",
            "/api/po/* - Purchase Order Management",
            "/api/stock/* - Stock Management",
            "/api/reports/* - Report Generation",
            "/api/uploads/* - File Uploads"
        ]
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint
    """
    logger.debug("Health check requested")
    
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = "unhealthy"
    
    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/cli/setup")
async def cli_setup():
    """
    CLI setup and information endpoint
    """
    print("🔧 CLI Setup Information")
    print("=" * 50)
    print(f"Application: {settings.APP_NAME}")
    print(f"Version: {settings.APP_VERSION}")
    print(f"Database: {settings.DATABASE_URL}")
    print(f"Debug Mode: {settings.DEBUG}")
    print()
    print("📋 Available CLI Commands:")
    print("  python -m app.cli.commands --help")
    print()
    print("🚀 Quick Start:")
    print("  1. Run migrations: alembic upgrade head")
    print("  2. Start server: uvicorn app.main:app --reload")
    print("  3. Default admin: admin / Admin@123")
    print("=" * 50)
    
    return {
        "message": "CLI setup information",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database_url": settings.DATABASE_URL[:50] + "..." if len(settings.DATABASE_URL) > 50 else settings.DATABASE_URL,
        "debug": settings.DEBUG
    }

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled Exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

# Import datetime for health check
from datetime import datetime
from fastapi.responses import JSONResponse

# Main execution
if __name__ == "__main__":
    print("🚀 Starting Construction Inventory System Backend")
    print(f"📝 Application: {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"🔧 Debug Mode: {settings.DEBUG}")
    print(f"🌐 Host: http://localhost:8000")
    print(f"📚 API Docs: http://localhost:8000/api/docs")
    print()
    print("📋 Available Routes:")
    print("  /api/auth/* - Authentication endpoints")
    print("  /api/users/* - User management")
    print("  /api/products/* - Material management")
    print("  /api/projects/* - Project management")
    print("  /api/sites/* - Site management")
    print("  /api/po/* - Purchase order management")
    print("  /api/stock/* - Stock management")
    print("  /api/reports/* - Report generation")
    print("  /api/uploads/* - File uploads")
    print()
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )
