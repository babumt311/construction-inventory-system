"""
Configuration settings for the application
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Construction Inventory System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:password@localhost:5432/construction_inventory"
    )

    # Force all tasks to go to 'default' queue automatically
    CELERY_TASK_DEFAULT_QUEUE: str= 'default'
    CELERY_TASK_ALWAYS_EAGER: bool= False

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Upload settings
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: set = {".xlsx", ".xls", ".csv"}

    # CORS
    BACKEND_CORS_ORIGINS: list = [
        "http://localhost:4200",  # Angular dev server
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # Redis for Celery (optional)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    class Config:
        env_file = ".env"

settings = Settings()
