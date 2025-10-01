from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from leaves.models import Department, LeaveType
from leaves.utils import setup_default_leave_types, initialize_user_leave_balances
from decimal import Decimal
from datetime import date

User = get_user_model()


class Command(BaseCommand):
    help = 'Set up initial data for the leave management system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up initial data...'))
        
        # Create default leave types
        self.stdout.write('Creating default leave types...')
        setup_default_leave_types()
        
        # Create departments
        self.stdout.write('Creating departments...')
        departments = [
            ('Human Resources', 'Manages employee relations and policies'),
            ('Information Technology', 'Develops and maintains IT systems'),
            ('Finance', 'Manages financial operations and accounting'),
            ('Marketing', 'Handles marketing and promotional activities'),
            ('Operations', 'Manages day-to-day business operations'),
        ]
        
        for dept_name, dept_desc in departments:
            dept, created = Department.objects.get_or_create(
                name=dept_name,
                defaults={'description': dept_desc}
            )
            if created:
                self.stdout.write(f'Created department: {dept_name}')
        
        # Create sample users
        self.stdout.write('Creating sample users...')
        
        # Create superuser/management user
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_user(
                username='admin',
                email='admin@company.com',
                password='admin123',
                first_name='System',
                last_name='Administrator',
                role='MANAGEMENT',
                hire_date=date(2023, 1, 1),
                is_staff=True,
                is_superuser=True
            )
            self.stdout.write(f'Created admin user: admin/admin123 (ID: {admin_user.employee_id})')
        
        # Get departments for user assignment
        hr_dept = Department.objects.get(name='Human Resources')
        it_dept = Department.objects.get(name='Information Technology')
        finance_dept = Department.objects.get(name='Finance')
        
        # Create HOD users
        hod_users = [
            {
                'username': 'hr_head',
                'email': 'hr.head@company.com',
                'password': 'password123',
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'role': 'HOD',
                'department': hr_dept,
                'hire_date': date(2023, 2, 1),
                'gender': 'F',
            },
            {
                'username': 'it_head',
                'email': 'it.head@company.com',
                'password': 'password123',
                'first_name': 'Michael',
                'last_name': 'Chen',
                'role': 'HOD',
                'department': it_dept,
                'hire_date': date(2023, 3, 1),
                'gender': 'M',
            },
            {
                'username': 'finance_head',
                'email': 'finance.head@company.com',
                'password': 'password123',
                'first_name': 'Emily',
                'last_name': 'Davis',
                'role': 'HOD',
                'department': finance_dept,
                'hire_date': date(2023, 2, 15),
                'gender': 'F',
            },
        ]
        
        for user_data in hod_users:
            if not User.objects.filter(username=user_data['username']).exists():
                user = User.objects.create_user(**user_data)
                self.stdout.write(f'Created HOD user: {user_data["username"]}/password123 (ID: {user.employee_id})')
        
        # Create regular employees
        from datetime import datetime
        current_date = datetime.now().date()
        
        employees = [
            {
                'username': 'john_doe',
                'email': 'john.doe@company.com',
                'password': 'password123',
                'first_name': 'John',
                'last_name': 'Doe',
                'role': 'EMPLOYEE',
                'department': it_dept,
                'hire_date': date(2023, 4, 1),  # Eligible for leave
                'gender': 'M',
            },
            {
                'username': 'jane_smith',
                'email': 'jane.smith@company.com',
                'password': 'password123',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'role': 'EMPLOYEE',
                'department': hr_dept,
                'hire_date': date(2023, 5, 15),  # Eligible for leave
                'gender': 'F',
            },
            {
                'username': 'bob_wilson',
                'email': 'bob.wilson@company.com',
                'password': 'password123',
                'first_name': 'Bob',
                'last_name': 'Wilson',
                'role': 'EMPLOYEE',
                'department': finance_dept,
                'hire_date': date(2023, 6, 1),  # Eligible for leave
                'gender': 'M',
            },
            {
                'username': 'new_employee',
                'email': 'new.employee@company.com',
                'password': 'password123',
                'first_name': 'New',
                'last_name': 'Employee',
                'role': 'EMPLOYEE',
                'department': it_dept,
                'hire_date': current_date,  # On probation
                'gender': 'F',
            },
        ]
        
        for user_data in employees:
            if not User.objects.filter(username=user_data['username']).exists():
                user = User.objects.create_user(**user_data)
                self.stdout.write(f'Created employee: {user_data["username"]}/password123 (ID: {user.employee_id})')
        
        # Initialize leave balances for all users
        self.stdout.write('Initializing leave balances...')
        for user in User.objects.filter(is_active=True):
            initialize_user_leave_balances(user)
            self.stdout.write(f'Initialized leave balances for {user.username}')
        
        self.stdout.write(self.style.SUCCESS('Initial data setup completed!'))
        self.stdout.write('')
        self.stdout.write('Sample login credentials:')
        self.stdout.write('  Admin (Management): admin/admin123')
        self.stdout.write('  HR Head (HOD): hr_head/password123')
        self.stdout.write('  IT Head (HOD): it_head/password123')
        self.stdout.write('  Finance Head (HOD): finance_head/password123')
        self.stdout.write('  Employee: john_doe/password123')
        self.stdout.write('  Employee: jane_smith/password123')
        self.stdout.write('  Employee: bob_wilson/password123')
