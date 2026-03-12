"""
CLI commands for the Construction Inventory System
"""
import click
import logging
from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import SessionLocal, engine, Base
from app import crud, models, schemas
from app.auth import cli_authenticate_user, create_admin_user, get_password_hash
from app.utils.stock_calculator import cli_calculate_stock, cli_generate_daily_report
from app.utils.excel_processor import cli_generate_template, cli_validate_file_format
from app.utils.report_generator import cli_generate_report

# Configure logging for CLI
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

@click.group()
def cli():
    """Construction Inventory System CLI"""
    pass

@cli.command()
def init_db():
    """Initialize the database"""
    click.echo("🗄️ Initializing database...")
    
    try:
        Base.metadata.create_all(bind=engine)
        click.echo("✅ Database tables created")
        
        # Create default admin user
        db = SessionLocal()
        create_admin_user(db)
        db.close()
        
        click.echo("✅ Default admin user created")
        click.echo("👑 Username: admin")
        click.echo("🔑 Password: Admin@123")
        
    except Exception as e:
        click.echo(f"❌ Error initializing database: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
def check_db():
    """Check database connection and status"""
    click.echo("🔍 Checking database status...")
    
    db = SessionLocal()
    try:
        # Test connection
        result = db.execute("SELECT version();").fetchone()
        click.echo(f"✅ Database connected: {result[0]}")
        
        # Count records
        user_count = db.query(models.User).count()
        project_count = db.query(models.Project).count()
        material_count = db.query(models.Material).count()
        
        click.echo(f"📊 Records:")
        click.echo(f"  👥 Users: {user_count}")
        click.echo(f"  🏗️  Projects: {project_count}")
        click.echo(f"  📦 Materials: {material_count}")
        
    except Exception as e:
        click.echo(f"❌ Database error: {str(e)}", err=True)
    finally:
        db.close()

@cli.command()
@click.option('--username', prompt=True, help='Username')
@click.option('--password', prompt=True, hide_input=True, help='Password')
def login(username, password):
    """Login and get access token"""
    click.echo(f"🔐 Attempting login for: {username}")
    
    db = SessionLocal()
    try:
        result = cli_authenticate_user(db, username, password)
        if result:
            click.echo("\n✅ Login successful!")
            click.echo(f"📝 Token: {result['access_token'][:50]}...")
            click.echo(f"👤 User: {result['user'].username}")
            click.echo(f"🎭 Role: {result['user'].role.value}")
        else:
            click.echo("❌ Login failed")
    finally:
        db.close()

@cli.command()
@click.option('--username', prompt=True, help='Username')
@click.option('--email', prompt=True, help='Email')
@click.option('--password', prompt=True, hide_input=True, help='Password')
@click.option('--role', type=click.Choice(['admin', 'owner', 'user']), default='user', help='User role')
def create_user(username, email, password, role):
    """Create a new user"""
    click.echo(f"👥 Creating user: {username}")
    
    db = SessionLocal()
    try:
        # Check if user exists
        existing = crud.crud_user.get_by_username(db, username=username)
        if existing:
            click.echo(f"❌ User {username} already exists")
            return
        
        existing = crud.crud_user.get_by_email(db, email=email)
        if existing:
            click.echo(f"❌ Email {email} already registered")
            return
        
        # Create user
        user_data = schemas.UserCreate(
            username=username,
            email=email,
            password=password,
            role=schemas.UserRole(role)
        )
        
        user = crud.crud_user.create(db, obj_in=user_data)
        click.echo(f"✅ User created successfully!")
        click.echo(f"   ID: {user.id}")
        click.echo(f"   Username: {user.username}")
        click.echo(f"   Email: {user.email}")
        click.echo(f"   Role: {user.role.value}")
        
    except Exception as e:
        click.echo(f"❌ Error creating user: {str(e)}", err=True)
    finally:
        db.close()

@cli.command()
def list_users():
    """List all users"""
    click.echo("👥 Listing all users:")
    
    db = SessionLocal()
    try:
        crud.cli_list_users(db)
    finally:
        db.close()

@cli.command()
def list_projects():
    """List all projects"""
    click.echo("🏗️  Listing all projects:")
    
    db = SessionLocal()
    try:
        crud.cli_list_projects(db)
    finally:
        db.close()

@cli.command()
def stats():
    """Show database statistics"""
    click.echo("📊 Database Statistics:")
    
    db = SessionLocal()
    try:
        crud.cli_show_stats(db)
    finally:
        db.close()

@cli.command()
@click.option('--site-id', required=True, type=int, help='Site ID')
@click.option('--material-id', required=True, type=int, help='Material ID')
def calculate_stock(site_id, material_id):
    """Calculate stock balance for a material at a site"""
    click.echo(f"🧮 Calculating stock balance...")
    
    db = SessionLocal()
    try:
        result = cli_calculate_stock(db, site_id, material_id)
        return result
    finally:
        db.close()

@cli.command()
@click.option('--site-id', required=True, type=int, help='Site ID')
@click.option('--date', type=click.DateTime(formats=["%Y-%m-%d"]), 
              default=str(date.today()), help='Report date (YYYY-MM-DD)')
def generate_report(site_id, date):
    """Generate daily stock report for a site"""
    click.echo(f"📋 Generating daily report...")
    
    db = SessionLocal()
    try:
        reports = cli_generate_daily_report(db, site_id, date.date())
        return reports
    finally:
        db.close()

@cli.command()
def generate_template():
    """Generate Excel template for material upload"""
    click.echo("📄 Generating material upload template...")
    
    try:
        template_path = cli_generate_template()
        click.echo(f"✅ Template generated: {template_path}")
    except Exception as e:
        click.echo(f"❌ Error generating template: {str(e)}", err=True)

@cli.command()
@click.argument('file_path')
def validate_file(file_path):
    """Validate Excel/CSV file format"""
    click.echo(f"🔍 Validating file: {file_path}")
    
    try:
        success = cli_validate_file_format(file_path)
        if success:
            click.echo("✅ File format is valid")
        else:
            click.echo("❌ File format is invalid")
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error validating file: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--type', required=True, 
              type=click.Choice(['material-wise', 'supplier-wise', 
                               'supplier-summary', 'stock-valuation']),
              help='Report type')
@click.option('--project-id', type=int, help='Project ID')
@click.option('--site-id', type=int, help='Site ID')
@click.option('--supplier', help='Supplier name')
def generate_report(type, project_id, site_id, supplier):
    """Generate various reports"""
    click.echo(f"📊 Generating {type} report...")
    
    db = SessionLocal()
    try:
        kwargs = {
            'project_id': project_id,
            'site_id': site_id,
            'supplier_name': supplier
        }
        report_data = cli_generate_report(db, type, **kwargs)
        return report_data
    finally:
        db.close()

@cli.command()
@click.option('--username', required=True, help='Username to reset')
@click.option('--new-password', prompt=True, hide_input=True, 
              confirmation_prompt=True, help='New password')
def reset_password(username, new_password):
    """Reset user password"""
    click.echo(f"🔑 Resetting password for: {username}")
    
    db = SessionLocal()
    try:
        user = crud.crud_user.get_by_username(db, username=username)
        if not user:
            click.echo(f"❌ User not found: {username}")
            return
        
        user.hashed_password = get_password_hash(new_password)
        db.add(user)
        db.commit()
        
        click.echo(f"✅ Password reset successfully for {username}")
        
    except Exception as e:
        click.echo(f"❌ Error resetting password: {str(e)}", err=True)
        db.rollback()
    finally:
        db.close()

@cli.command()
def system_info():
    """Display system information"""
    click.echo("🏗️ Construction Inventory System")
    click.echo("=" * 50)
    click.echo("📋 System Information:")
    click.echo("  Backend: FastAPI")
    click.echo("  Database: PostgreSQL")
    click.echo("  Frontend: Angular (separate)")
    click.echo("  Authentication: JWT + RBAC")
    click.echo()
    click.echo("🚀 Available Commands:")
    click.echo("  init-db        - Initialize database")
    click.echo("  check-db       - Check database status")
    click.echo("  login          - Login and get token")
    click.echo("  create-user    - Create new user")
    click.echo("  list-users     - List all users")
    click.echo("  list-projects  - List all projects")
    click.echo("  stats          - Show statistics")
    click.echo("  calculate-stock - Calculate stock balance")
    click.echo("  generate-report - Generate daily report")
    click.echo("  generate-template - Generate Excel template")
    click.echo("  validate-file  - Validate Excel file")
    click.echo("  reset-password - Reset user password")
    click.echo("=" * 50)

if __name__ == '__main__':
    cli()
