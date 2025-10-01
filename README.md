# Leave Management System

A comprehensive Django-based leave management system with Docker support.

## Features

- **User Roles**: Employee, HOD (Head of Department), Management
- **Leave Types**: Annual leave (accrual-based), Sick leave, Study leave, Paternity leave, Maternity leave
- **Gender-Based Leave Allocation**: Automatic allocation of paternity leave for males and maternity leave for females
- **Probation Period**: New employees must complete 6 months before being eligible for leave
- **Approval Workflow**: Two-tier approval system (HOD → Management)
- **Leave Calculation**: 
  - Annual leave: 1.75 days per month starting from 7th month (after probation)
  - Working days counting for Annual/Sick/Study leave
  - All days counting for Paternity/Maternity leave
- **Manual Override**: Admins can manually set leave balances and probation end dates
- **Leave Recall**: Management can recall approved leaves
- **Enhanced Dashboard**: Modern UI with probation status, leave eligibility, and visual indicators
- **Admin Interface**: Management users can create users, set manual leave balances, and manage leave types

## Quick Start with Docker

1. **Clone and navigate to the project directory:**
   ```bash
   cd /home/paul/development/leave_management_system
   ```

2. **Build and start the services:**
   ```bash
   docker-compose up --build
   ```

3. **In a new terminal, run migrations and setup initial data:**
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py setup_initial_data
   ```

4. **Access the application:**
   - Web Interface: http://localhost:8000
   - Admin Interface: http://localhost:8000/admin

## Manual Setup (without Docker)

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup database:**
   ```bash
   python manage.py migrate
   python manage.py setup_initial_data
   ```

4. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

## Sample Login Credentials

After running `setup_initial_data`, use these credentials:

### Management Level
- **Username**: admin
- **Password**: admin123
- **Role**: Management (full access)

### Head of Department (HOD)
- **Username**: hr_head
- **Password**: password123
- **Department**: Human Resources

- **Username**: it_head
- **Password**: password123
- **Department**: Information Technology

- **Username**: finance_head
- **Password**: password123
- **Department**: Finance

### Regular Employees
- **Username**: john_doe
- **Password**: password123
- **Department**: Information Technology

- **Username**: jane_smith
- **Password**: password123
- **Department**: Human Resources

- **Username**: bob_wilson
- **Password**: password123
- **Department**: Finance

- **Username**: new_employee (On Probation)
- **Password**: password123
- **Department**: Information Technology
- **Note**: This user is on probation and not eligible for leave

## System Architecture

### User Hierarchy
1. **Management**: Can approve all leaves, create users, manage system
2. **HOD**: Can approve leaves for department employees (except other HODs)
3. **Employee**: Can request and view their own leaves

### Leave Types Configuration
- **Annual Leave**: 1.75 days/month accrual, working days only
- **Sick Leave**: 7 days/year, working days only
- **Study Leave**: 3 days/year, working days only
- **Paternity Leave**: 14 days/year, all days including weekends
- **Maternity Leave**: 90 days/year, all days including weekends

### Approval Workflow
1. Employee submits leave request
2. HOD reviews and approves/rejects (for regular employees)
3. Management gives final approval
4. For HOD leave requests, they go directly to Management

### Key Features
- **Real-time Dashboard**: Shows current leave status, balances, pending approvals
- **Automatic Calculations**: Working days vs all days based on leave type
- **Leave Recall**: Management can recall approved leaves and restore unused days
- **Balance Tracking**: Automatic tracking of allocated, used, and pending days
- **Monthly Accrual**: Celery tasks for automatic annual leave accrual

## Development

### Project Structure
```
leave_management_system/
├── leave_management/          # Django project settings
├── leaves/                    # Main application
│   ├── models.py             # Database models
│   ├── views.py              # Views and business logic
│   ├── forms.py              # Django forms
│   ├── admin.py              # Admin interface
│   ├── utils.py              # Utility functions
│   ├── tasks.py              # Celery tasks
│   └── urls.py               # URL routing
├── templates/                 # HTML templates
├── static/                    # Static files
├── docker-compose.yml         # Docker configuration
└── requirements.txt           # Python dependencies
```

### Technology Stack
- **Backend**: Django 5.2.6
- **Database**: PostgreSQL 15
- **Task Queue**: Celery with Redis
- **Frontend**: Bootstrap 5 + jQuery
- **Containerization**: Docker & Docker Compose

### Celery Tasks
The system includes Celery tasks for:
- Monthly leave accrual calculation
- Leave balance initialization for new users

To start Celery services:
```bash
# Worker
celery -A leave_management worker --loglevel=info

# Beat scheduler
celery -A leave_management beat --loglevel=info
```

## API Endpoints

### Main Views
- `/` - Dashboard
- `/request/` - Request leave
- `/requests/` - View leave requests
- `/approvals/` - Approval dashboard (HOD/Management)
- `/who-is-on-leave/` - Current leave status
- `/leave-balance/` - Leave balance view

### AJAX Endpoints
- `/ajax/calculate-days/` - Calculate leave days

## Admin Interface

Management users can access the admin interface at `/admin/` to:
- Create and manage users
- Create custom leave types
- View and manage leave requests
- Monitor leave balances
- View leave allocations

## Environment Variables

Key environment variables (configured in `.env`):
- `DEBUG`: Debug mode (True/False)
- `SECRET_KEY`: Django secret key
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection for Celery

## Production Deployment Notes

1. Set `DEBUG=False` in production
2. Configure proper SECRET_KEY
3. Set up proper database (PostgreSQL recommended)
4. Configure Redis for Celery tasks
5. Set up proper static file serving
6. Configure email backend for notifications (optional)
7. Set up proper logging

## Troubleshooting

### Common Issues

1. **Database connection errors**: Check PostgreSQL service and credentials
2. **Migration errors**: Run `python manage.py migrate` after model changes
3. **Celery tasks not running**: Ensure Redis is running and Celery workers are started
4. **Permission errors**: Check user roles and department assignments

### Development Commands

```bash
# Create new migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load initial data
python manage.py setup_initial_data

# Run tests (when implemented)
python manage.py test

# Collect static files
python manage.py collectstatic
```

## License

This project is created as a demonstration of Django leave management system capabilities.
# Leave-Management-System
