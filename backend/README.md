# Construction Site Material Inventory Management System

A comprehensive backend system for managing construction site material inventory built with FastAPI.

## Features

- **User Management**: Role-based access control (Admin, Owner, User) with JWT authentication
- **Material Database**: Product and category management with Excel/CSV upload
- **Project & Site Management**: Hierarchical structure (Projects → Sites)
- **Inventory Tracking**: Purchase orders, stock entries, and real-time stock calculations
- **Reporting**: Material-wise, supplier-wise, and time-based reports (daily, weekly, monthly, annual)
- **Audit Logging**: Comprehensive logging of all data-changing actions
- **RESTful API**: Complete API documentation with Swagger UI

## Tech Stack

- **Backend**: FastAPI (Python 3.9+)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT with Passlib (bcrypt)
- **Migrations**: Alembic
- **Task Queue**: Celery with Redis (optional)
- **Containerization**: Docker & Docker Compose

## Installation

### Prerequisites
- Python 3.9+
- PostgreSQL 13+
- Redis (optional, for background tasks)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/construction-inventory-system.git
   cd construction-inventory-system
