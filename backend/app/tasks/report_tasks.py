"""
Report generation tasks
"""
from celery import shared_task
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
import logging
from app.database import SessionLocal
from app import models
from app.utils.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def generate_weekly_reports(self):
    """
    Generate weekly reports for all projects
    """
    logger.info("Starting weekly report generation")
    
    try:
        db = SessionLocal()
        generator = ReportGenerator()
        
        today = date.today()
        start_date = today - timedelta(days=today.weekday() + 7)
        end_date = start_date + timedelta(days=6)
        
        projects = db.query(models.Project).filter(
            models.Project.status == 'active'
        ).all()
        
        reports_generated = []
        
        for project in projects:
            try:
                material_report = generator.generate_material_wise_report(
                    db, project.id, start_date, end_date
                )
                
                supplier_report = generator.generate_supplier_wise_report(
                    db, project.id, None, start_date, end_date
                )
                
                reports_generated.append({
                    'project_id': project.id,
                    'project_name': project.name,
                    'material_report_count': len(material_report),
                    'supplier_report_count': len(supplier_report)
                })
                
            except Exception as e:
                logger.error(f"Failed to generate weekly reports for project {project.id}: {str(e)}")
                continue
        
        db.close()
        
        return {
            'status': 'completed',
            'task_id': self.request.id,
            'week_start': start_date.isoformat(),
            'week_end': end_date.isoformat(),
            'reports_generated': len(reports_generated),
            'details': reports_generated,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Weekly report generation failed: {str(e)}")
        return {
            'status': 'failed',
            'task_id': self.request.id,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

@shared_task(bind=True)
def generate_monthly_reports(self):
    """
    Generate monthly reports for all projects
    """
    logger.info("Starting monthly report generation")
    
    try:
        db = SessionLocal()
        generator = ReportGenerator()
        
        today = date.today()
        if today.month == 1:
            start_date = date(today.year - 1, 12, 1)
        else:
            start_date = date(today.year, today.month - 1, 1)
        
        import calendar
        last_day = calendar.monthrange(start_date.year, start_date.month)[1]
        end_date = date(start_date.year, start_date.month, last_day)
        
        projects = db.query(models.Project).filter(
            models.Project.status == 'active'
        ).all()
        
        reports_generated = []
        total_cost = 0
        
        for project in projects:
            try:
                material_report = generator.generate_material_wise_report(
                    db, project.id, start_date, end_date
                )
                
                monthly_cost = sum(item['total_cost'] for item in material_report)
                total_cost += monthly_cost
                
                reports_generated.append({
                    'project_id': project.id,
                    'project_name': project.name,
                    'monthly_cost': float(monthly_cost),
                    'material_count': len(material_report)
                })
                
            except Exception as e:
                logger.error(f"Failed to generate monthly reports for project {project.id}: {str(e)}")
                continue
        
        db.close()
        
        return {
            'status': 'completed',
            'task_id': self.request.id,
            'month': start_date.strftime('%Y-%m'),
            'total_projects': len(projects),
            'total_monthly_cost': float(total_cost),
            'reports_generated': len(reports_generated),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Monthly report generation failed: {str(e)}")
        return {
            'status': 'failed',
            'task_id': self.request.id,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }
