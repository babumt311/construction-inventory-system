"""
Daily scheduled tasks
"""
from celery import shared_task
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
import logging
from app.database import SessionLocal
from app import models
from app.utils.stock_calculator import StockCalculator

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def generate_daily_stock_reports(self):
    """
    Generate daily stock reports for all active sites
    """
    logger.info("Starting daily stock report generation")
    
    try:
        db = SessionLocal()
        today = date.today()
        report_date = today - timedelta(days=1)  # Report for yesterday
        
        # Get all active sites
        sites = db.query(models.Site).filter(
            models.Site.status == 'active'
        ).all()
        
        total_reports = 0
        calculator = StockCalculator()
        
        for site in sites:
            try:
                reports = calculator.generate_daily_report(db, site.id, report_date)
                total_reports += len(reports)
                logger.info(f"Generated {len(reports)} reports for site {site.name}")
            except Exception as e:
                logger.error(f"Failed to generate reports for site {site.id}: {str(e)}")
                continue
        
        db.close()
        
        return {
            'status': 'completed',
            'task_id': self.request.id,
            'date': str(report_date),
            'total_sites': len(sites),
            'total_reports': total_reports,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Daily stock report generation failed: {str(e)}")
        return {
            'status': 'failed',
            'task_id': self.request.id,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

@shared_task(bind=True)
def send_stock_alerts(self):
    """
    Send stock alerts for low stock or negative balance
    """
    logger.info("Starting stock alerts task")
    
    try:
        db = SessionLocal()
        calculator = StockCalculator()
        alerts = []
        
        # Get all active sites
        sites = db.query(models.Site).filter(
            models.Site.status == 'active'
        ).all()
        
        for site in sites:
            try:
                summary = calculator.get_site_stock_summary(db, site.id)
                
                for item in summary:
                    if item['has_negative_balance']:
                        alerts.append({
                            'site': site.name,
                            'material': item['material_name'],
                            'current_balance': float(item['current_balance']),
                            'type': 'negative_balance'
                        })
                    
                    elif item['current_balance'] < 10:  # Low stock threshold
                        alerts.append({
                            'site': site.name,
                            'material': item['material_name'],
                            'current_balance': float(item['current_balance']),
                            'type': 'low_stock'
                        })
                        
            except Exception as e:
                logger.error(f"Error checking stock for site {site.id}: {str(e)}")
                continue
        
        db.close()
        
        # In production, send email notifications here
        if alerts:
            logger.warning(f"Found {len(alerts)} stock alerts that need attention")
        
        return {
            'status': 'completed',
            'task_id': self.request.id,
            'total_alerts': len(alerts),
            'alerts': alerts,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Stock alerts task failed: {str(e)}")
        return {
            'status': 'failed',
            'task_id': self.request.id,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

@shared_task(bind=True)
def cleanup_old_audit_logs(self, days_to_keep=90):
    """
    Cleanup old audit logs
    """
    logger.info(f"Starting audit log cleanup (keeping {days_to_keep} days)")
    
    try:
        db = SessionLocal()
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        deleted_count = db.query(models.AuditLog).filter(
            models.AuditLog.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        db.commit()
        db.close()
        
        logger.info(f"Deleted {deleted_count} old audit logs")
        
        return {
            'status': 'completed',
            'task_id': self.request.id,
            'deleted_records': deleted_count,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Audit log cleanup failed: {str(e)}")
        db.rollback()
        return {
            'status': 'failed',
            'task_id': self.request.id,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }
