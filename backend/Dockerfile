# ============================================
# Dockerfile for Construction Inventory System
# Includes FastAPI backend + Celery worker/beat
# ============================================

# Stage 1: Base image with Python and system dependencies
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Build dependencies
    gcc \
    g++ \
    make \
    # PostgreSQL client (for backups)
    postgresql-client \
    libpq-dev \
    # Utilities
    curl \
    wget \
    gnupg \
    ca-certificates \
    # Required for some Python packages
    libffi-dev \
    libssl-dev \
    # For health checks
    netcat-openbsd \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements files
COPY requirements.txt .
COPY requirements-celery.txt ./

RUN mkdir -p /var/log/supervisor \
    && chmod -R 777 /var/log/supervisor

# ============================================
# Stage 2: Development stage (optional)
# ============================================
FROM base AS development

# Install development dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-celery.txt

# Copy application code
COPY . .

# Create directories with proper permissions
RUN mkdir -p /app/uploads /app/logs /app/backups /app/exports && \
    chmod -R 755 /app/uploads /app/logs /app/backups /app/exports

# Create non-root user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -d /home/appuser -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (FastAPI)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ============================================
# Stage 3: Production stage for FastAPI
# ============================================
FROM base AS production-backend

# Install production dependencies only
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy only necessary files
COPY --chown=appuser:appuser . .

# Create directories
RUN mkdir -p /app/uploads /app/logs /app/backups /app/exports && \
    chmod -R 755 /app/uploads /app/logs /app/backups /app/exports

# Create non-root user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -d /home/appuser -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ============================================
# Stage 4: Production stage for Celery Worker
# ============================================
FROM base AS production-celery-worker

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-celery.txt

# Copy application code
COPY --chown=appuser:appuser . .

# Create directories
RUN mkdir -p /app/uploads /app/logs /app/backups /app/exports && \
    chmod -R 755 /app/uploads /app/logs /app/backups /app/exports

# Create non-root user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -d /home/appuser -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check for Celery worker
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD celery -A app.tasks.celery_app inspect ping -d celery@$HOSTNAME || exit 1

# Default command for Celery worker
CMD ["celery", "-A", "app.tasks.celery_app", "worker", \
     "--loglevel=info", \
     "--concurrency=4", \
     "--max-tasks-per-child=100", \
     "--maxtasksperchild=100", \
     "--autoscale=10,3"]

# ============================================
# Stage 5: Production stage for Celery Beat
# ============================================
FROM base AS production-celery-beat

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-celery.txt

# Copy application code
COPY --chown=appuser:appuser . .

# Create directories
RUN mkdir -p /app/uploads /app/logs /app/backups /app/exports && \
    chmod -R 755 /app/uploads /app/logs /app/backups /app/exports

# Create non-root user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -d /home/appuser -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check for Celery beat
HEALTHCHECK --interval=30s --timeout=30s --start-period=10s --retries=3 \
    CMD [ -f /tmp/celerybeat-schedule ] || exit 1

# Create schedule directory
RUN mkdir -p /var/run/celery && \
    chown -R appuser:appuser /var/run/celery

# Default command for Celery beat
CMD ["celery", "-A", "app.tasks.celery_app", "beat", \
     "--loglevel=info", \
     "--schedule=/tmp/celerybeat-schedule", \
     "--pidfile=/tmp/celerybeat.pid"]

# ============================================
# Stage 6: All-in-one image (for development)
# ============================================
FROM base AS all-in-one

# Install all dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-celery.txt && \
    pip install --no-cache-dir supervisor

# Copy application code
COPY . .

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create directories
RUN mkdir -p /app/uploads /app/logs /app/backups /app/exports /var/log/supervisor && \
    chmod -R 755 /app/uploads /app/logs /app/backups /app/exports /var/log/supervisor

# Create non-root user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -d /home/appuser -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start all services with supervisor
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
