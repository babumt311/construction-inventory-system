"""
Celery application configuration
"""
from app.tasks import daily_tasks, report_tasks
import os
from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Set default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.config')

# Create Celery app
celery_app = Celery(
    'construction_inventory',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
include=[
        'app.tasks.daily_tasks', 
        'app.tasks.report_tasks',
        # Add any other files containing tasks here
    ]
)

# Configure Celery using settings module
celery_app.config_from_object('app.config:settings', namespace='CELERY')

# Auto-discover tasks
celery_app.autodiscover_tasks(['app.tasks'])

# Configure beat schedule
celery_app.conf.beat_schedule = {
    # Daily stock report generation at 11:59 PM
    'generate-daily-reports': {
        'task': 'app.tasks.daily_tasks.generate_daily_stock_reports',
        'schedule': crontab(hour=23, minute=59),
    },
    
    # Weekly report generation on Sunday at 12:00 AM
    'generate-weekly-reports': {
        'task': 'app.tasks.report_tasks.generate_weekly_reports',
        'schedule': crontab(hour=0, minute=0, day_of_week=0),  # Sunday
    },
    
    # Monthly report generation on 1st day of month at 12:00 AM
    'generate-monthly-reports': {
        'task': 'app.tasks.report_tasks.generate_monthly_reports',
        'schedule': crontab(hour=0, minute=0, day_of_month='1'),
    },
    
    # Cleanup old audit logs (keep 90 days only)
    'cleanup-old-audit-logs': {
        'task': 'app.tasks.daily_tasks.cleanup_old_audit_logs',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'args': (90,),  # Keep 90 days
    },
    
    # Send daily stock alerts at 9 AM
    'send-stock-alerts': {
        'task': 'app.tasks.daily_tasks.send_stock_alerts',
        'schedule': crontab(hour=9, minute=0),
    }
}

# Celery Configuration Updates
celery_app.conf.update(
    timezone='UTC',
    broker_connection_retry_on_startup=True,  # <--- ADD THIS LINE
)

celery_app.conf.timezone = 'UTC'

@celery_app.task(bind=True)
def debug_task(self):
    """Debug task to check Celery is working"""
    print(f'Request: {self.request!r}')
    return {'status': 'success', 'task_id': self.request.id}
