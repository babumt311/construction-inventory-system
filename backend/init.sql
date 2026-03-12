-- Initial database setup script
-- This script runs when PostgreSQL container is created

-- Create extension for UUID if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set timezone
SET timezone = 'UTC';

-- Create additional indexes for performance (optional)
-- Note: Actual indexes are created by SQLAlchemy models
-- This file can be extended for custom database setup
