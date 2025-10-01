from datetime import datetime, timedelta, date
from decimal import Decimal
import calendar
from django.utils import timezone
from .models import LeaveBalance, LeaveType, LeaveAllocation, User


def calculate_working_days(start_date, end_date):
    """
    Calculate the number of working days (Monday to Friday) between two dates, inclusive.
    """
    if start_date > end_date:
        return 0
    
    working_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        # Monday = 0, Sunday = 6, so weekdays are 0-4
        if current_date.weekday() < 5:
            working_days += 1
        current_date += timedelta(days=1)
    
    return working_days


def calculate_all_days(start_date, end_date):
    """
    Calculate the total number of days between two dates, inclusive.
    """
    if start_date > end_date:
        return 0
    
    delta = end_date - start_date
    return delta.days + 1


def calculate_leave_days(start_date, end_date, leave_type):
    """
    Calculate the number of leave days based on the leave type's counting method.
    """
    if leave_type.counting_type == 'WORKING_DAYS':
        return calculate_working_days(start_date, end_date)
    else:
        return calculate_all_days(start_date, end_date)


def calculate_annual_leave_accrual(user, target_date=None):
    """
    Calculate annual leave accrual for a user up to a target date.
    Annual leave accrues at 1.75 days per month after the month ends.
    User must complete 6 months probation before accrual starts.
    """
    if not user.hire_date:
        return Decimal('0')
    
    if target_date is None:
        target_date = timezone.now().date()
    
    # Check if user has manual override
    if user.manual_annual_leave_balance is not None:
        return user.manual_annual_leave_balance
    
    # Find the annual leave type
    try:
        annual_leave_type = LeaveType.objects.get(name='Annual Leave', is_accrual=True)
    except LeaveType.DoesNotExist:
        return Decimal('0')
    
    accrual_rate = annual_leave_type.accrual_rate or Decimal('1.75')
    
    # Check if user is eligible for leave (past probation)
    if not user.is_eligible_for_leave(target_date):
        return Decimal('0')
    
    # Start accrual from probation end date (7th month)
    probation_end_date = user.get_probation_end_date()
    if not probation_end_date or probation_end_date > target_date:
        return Decimal('0')
    
    # Calculate full months completed since probation ended
    months_completed = 0
    # Start from the month after probation ends
    from dateutil.relativedelta import relativedelta
    current_date = probation_end_date.replace(day=1)
    
    while current_date <= target_date:
        # Check if the full month has ended
        last_day_of_month = calendar.monthrange(current_date.year, current_date.month)[1]
        month_end = current_date.replace(day=last_day_of_month)
        
        if month_end < target_date:
            months_completed += 1
        
        # Move to next month
        current_date = current_date + relativedelta(months=1)
    
    return Decimal(str(months_completed)) * accrual_rate


def get_or_create_leave_balance(user, leave_type, year=None):
    """
    Get or create a leave balance for a user and leave type for a specific year.
    """
    if year is None:
        year = timezone.now().year
    
    balance, created = LeaveBalance.objects.get_or_create(
        user=user,
        leave_type=leave_type,
        year=year,
        defaults={
            'allocated_days': Decimal('0'),
            'used_days': Decimal('0'),
            'pending_days': Decimal('0'),
        }
    )
    
    return balance


def initialize_user_leave_balances(user, year=None):
    """
    Initialize leave balances for a user for all active leave types.
    Only allocates leave types relevant to user's gender and eligibility.
    """
    if year is None:
        year = timezone.now().year
    
    active_leave_types = LeaveType.objects.filter(is_active=True)
    
    for leave_type in active_leave_types:
        # Skip gender-specific leave types if not applicable
        if leave_type.name == 'Paternity Leave' and user.gender != 'M':
            continue
        if leave_type.name == 'Maternity Leave' and user.gender != 'F':
            continue
        
        balance = get_or_create_leave_balance(user, leave_type, year)
        
        if leave_type.is_accrual:
            # Calculate accrual for annual leave
            if leave_type.name == 'Annual Leave':
                accrued_days = calculate_annual_leave_accrual(user)
                balance.allocated_days = accrued_days
        else:
            # Set fixed allocation for non-accrual leave types
            # Only if user is eligible for leave (past probation)
            if leave_type.max_days_per_year and user.is_eligible_for_leave():
                balance.allocated_days = leave_type.max_days_per_year
            elif not user.is_eligible_for_leave():
                balance.allocated_days = Decimal('0')
            else:
                balance.allocated_days = leave_type.max_days_per_year or Decimal('0')
        
        balance.save()


def update_annual_leave_accrual(user_id=None):
    """
    Update annual leave accrual for all users or a specific user.
    This should be run monthly via Celery task.
    """
    from .models import User
    
    if user_id:
        users = User.objects.filter(id=user_id, is_active=True)
    else:
        users = User.objects.filter(is_active=True)
    
    try:
        annual_leave_type = LeaveType.objects.get(name='Annual Leave', is_accrual=True)
    except LeaveType.DoesNotExist:
        return
    
    current_year = timezone.now().year
    
    for user in users:
        if not user.hire_date:
            continue
        
        # Calculate total accrued days
        total_accrued = calculate_annual_leave_accrual(user)
        
        # Get current balance
        balance = get_or_create_leave_balance(user, annual_leave_type, current_year)
        
        # Calculate new allocation (difference from current)
        new_allocation = total_accrued - balance.allocated_days
        
        if new_allocation > 0:
            # Create allocation record
            LeaveAllocation.objects.create(
                user=user,
                leave_type=annual_leave_type,
                allocation_date=timezone.now().date(),
                days_allocated=new_allocation,
                reason='Monthly accrual update'
            )
            
            # Update balance
            balance.allocated_days = total_accrued
            balance.save()


def setup_default_leave_types():
    """
    Set up the default leave types as specified in requirements.
    """
    default_leave_types = [
        {
            'name': 'Annual Leave',
            'description': 'Annual vacation leave that accrues at 1.75 days per month',
            'max_days_per_year': None,
            'is_accrual': True,
            'accrual_rate': Decimal('1.75'),
            'counting_type': 'WORKING_DAYS',
            'requires_documentation': False,
        },
        {
            'name': 'Sick Leave',
            'description': 'Medical leave for illness',
            'max_days_per_year': Decimal('7'),
            'is_accrual': False,
            'accrual_rate': None,
            'counting_type': 'WORKING_DAYS',
            'requires_documentation': True,
        },
        {
            'name': 'Study Leave',
            'description': 'Leave for educational purposes',
            'max_days_per_year': Decimal('3'),
            'is_accrual': False,
            'accrual_rate': None,
            'counting_type': 'WORKING_DAYS',
            'requires_documentation': True,
        },
        {
            'name': 'Paternity Leave',
            'description': 'Leave for new fathers',
            'max_days_per_year': Decimal('14'),
            'is_accrual': False,
            'accrual_rate': None,
            'counting_type': 'ALL_DAYS',
            'requires_documentation': True,
        },
        {
            'name': 'Maternity Leave',
            'description': 'Leave for new mothers',
            'max_days_per_year': Decimal('90'),
            'is_accrual': False,
            'accrual_rate': None,
            'counting_type': 'ALL_DAYS',
            'requires_documentation': True,
        },
    ]
    
    for leave_data in default_leave_types:
        LeaveType.objects.get_or_create(
            name=leave_data['name'],
            defaults=leave_data
        )


def can_user_request_leave(user, leave_type, start_date, end_date):
    """
    Check if a user can request a specific leave.
    Returns (can_request: bool, reason: str)
    """
    # Check if user is eligible for leave (past probation period)
    if not user.is_eligible_for_leave(start_date):
        probation_end_date = user.get_probation_end_date()
        if probation_end_date:
            return False, f"You are not eligible for leave until {probation_end_date.strftime('%B %d, %Y')} (6 months from hire date)"
        else:
            return False, "You are not eligible for leave during probation period"
    
    # Check gender-specific leave types
    if leave_type.name == 'Paternity Leave' and user.gender != 'M':
        return False, "Paternity leave is only available for male employees"
    
    if leave_type.name == 'Maternity Leave' and user.gender != 'F':
        return False, "Maternity leave is only available for female employees"
    
    # Calculate days requested
    days_requested = calculate_leave_days(start_date, end_date, leave_type)
    
    # Get current balance
    current_year = start_date.year
    balance = get_or_create_leave_balance(user, leave_type, current_year)
    
    # Check if enough days available
    if balance.available_days < days_requested:
        return False, f"Insufficient {leave_type.name} balance. Available: {balance.available_days}, Requested: {days_requested}"
    
    # Check if dates are valid
    if start_date < timezone.now().date():
        return False, "Cannot request leave for past dates"
    
    if start_date > end_date:
        return False, "Start date cannot be after end date"
    
    return True, "Leave request is valid"


def update_leave_balance_on_approval(leave_request):
    """
    Update leave balance when a request is approved.
    Move days from pending to used.
    """
    balance = get_or_create_leave_balance(
        leave_request.user,
        leave_request.leave_type,
        leave_request.start_date.year
    )
    
    balance.pending_days -= leave_request.days_requested
    balance.used_days += leave_request.days_requested
    balance.save()


def update_leave_balance_on_rejection(leave_request):
    """
    Update leave balance when a request is rejected.
    Remove days from pending.
    """
    balance = get_or_create_leave_balance(
        leave_request.user,
        leave_request.leave_type,
        leave_request.start_date.year
    )
    
    balance.pending_days -= leave_request.days_requested
    balance.save()


def update_leave_balance_on_recall(leave_request, days_to_restore):
    """
    Update leave balance when a leave is recalled.
    Move unused days back to available.
    """
    balance = get_or_create_leave_balance(
        leave_request.user,
        leave_request.leave_type,
        leave_request.start_date.year
    )
    
    balance.used_days -= days_to_restore
    balance.save()
