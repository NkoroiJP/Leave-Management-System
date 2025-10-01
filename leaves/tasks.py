from celery import shared_task
from django.utils import timezone
from .utils import update_annual_leave_accrual, initialize_user_leave_balances
from .models import User


@shared_task
def monthly_leave_accrual():
    """
    Monthly task to update annual leave accrual for all active users.
    This should be scheduled to run on the first day of each month.
    """
    update_annual_leave_accrual()
    return f"Annual leave accrual updated for all users on {timezone.now()}"


@shared_task
def initialize_new_user_leave_balances(user_id):
    """
    Initialize leave balances for a newly created user.
    """
    try:
        user = User.objects.get(id=user_id)
        initialize_user_leave_balances(user)
        return f"Leave balances initialized for user {user.username}"
    except User.DoesNotExist:
        return f"User with id {user_id} not found"


@shared_task
def update_single_user_accrual(user_id):
    """
    Update annual leave accrual for a single user.
    """
    try:
        user = User.objects.get(id=user_id)
        update_annual_leave_accrual(user_id)
        return f"Annual leave accrual updated for user {user.username}"
    except User.DoesNotExist:
        return f"User with id {user_id} not found"
