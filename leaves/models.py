from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import calendar


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']


class User(AbstractUser):
    ROLE_CHOICES = [
        ('EMPLOYEE', 'Employee'),
        ('HOD', 'Head of Department'),
        ('MANAGEMENT', 'Management'),
    ]
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='EMPLOYEE')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True)
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Manual leave allocation fields (for admin override)
    manual_annual_leave_balance = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Override annual leave balance (leave blank for automatic calculation)"
    )
    probation_end_date = models.DateField(
        null=True, blank=True,
        help_text="Date when employee becomes eligible for leave (auto-calculated as 6 months from hire date if not specified)"
    )
    
    def save(self, *args, **kwargs):
        # Auto-generate employee ID if not provided
        if not self.employee_id:
            # Get the latest employee ID number
            last_user = User.objects.filter(
                employee_id__startswith='EMP'
            ).exclude(employee_id__isnull=True).exclude(employee_id='').order_by('-employee_id').first()
            
            if last_user and last_user.employee_id:
                try:
                    # Extract number from last employee ID (e.g., EMP001 -> 1)
                    last_number = int(last_user.employee_id.replace('EMP', ''))
                    new_number = last_number + 1
                except (ValueError, AttributeError):
                    new_number = 1
            else:
                new_number = 1
            
            # Format as EMP001, EMP002, etc.
            self.employee_id = f"EMP{new_number:03d}"
        
        # Auto-set probation end date if not provided
        if self.hire_date and not self.probation_end_date:
            from dateutil.relativedelta import relativedelta
            self.probation_end_date = self.hire_date + relativedelta(months=6)
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.employee_id})"
    
    @property
    def is_hod(self):
        return self.role == 'HOD'
    
    @property
    def is_management(self):
        return self.role == 'MANAGEMENT'
    
    @property
    def is_employee(self):
        return self.role == 'EMPLOYEE'
    
    def can_approve_leave(self, leave_request):
        """Check if user can approve a leave request"""
        if self.is_management:
            return True
        if self.is_hod and leave_request.user.department == self.department:
            # HOD can approve if user is not HOD or if it's first level approval
            return not leave_request.user.is_hod
        return False
    
    def is_eligible_for_leave(self, target_date=None):
        """Check if user is eligible for leave (past probation period)"""
        if not self.hire_date:
            return False
        
        if target_date is None:
            target_date = timezone.now().date()
        
        # Check if probation_end_date is manually set
        if self.probation_end_date:
            return target_date >= self.probation_end_date
        
        # Auto-calculate: 6 months from hire date
        from dateutil.relativedelta import relativedelta
        probation_end = self.hire_date + relativedelta(months=6)
        return target_date >= probation_end
    
    def get_probation_end_date(self):
        """Get the probation end date"""
        if self.probation_end_date:
            return self.probation_end_date
        
        if self.hire_date:
            from dateutil.relativedelta import relativedelta
            return self.hire_date + relativedelta(months=6)
        
        return None
    
    @property
    def is_on_probation(self):
        """Check if user is currently on probation"""
        return not self.is_eligible_for_leave()
    
    class Meta:
        ordering = ['last_name', 'first_name']


class LeaveType(models.Model):
    """Different types of leave available"""
    COUNTING_TYPE_CHOICES = [
        ('WORKING_DAYS', 'Working Days Only (Mon-Fri)'),
        ('ALL_DAYS', 'All Days (Including Weekends)'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    max_days_per_year = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_accrual = models.BooleanField(default=False)  # For annual leave
    accrual_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # Days per month
    counting_type = models.CharField(max_length=20, choices=COUNTING_TYPE_CHOICES, default='WORKING_DAYS')
    requires_documentation = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']


class LeaveBalance(models.Model):
    """Track leave balances for each user and leave type"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.IntegerField()
    allocated_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    used_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    pending_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Days in pending requests
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'leave_type', 'year']
        ordering = ['user', 'leave_type', 'year']
    
    @property
    def available_days(self):
        return self.allocated_days - self.used_days - self.pending_days
    
    def __str__(self):
        return f"{self.user} - {self.leave_type} ({self.year}): {self.available_days} available"


class LeaveRequest(models.Model):
    """Individual leave requests"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('HOD_APPROVED', 'HOD Approved'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('RECALLED', 'Recalled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Approval workflow
    hod_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='hod_approved_requests')
    hod_approved_at = models.DateTimeField(null=True, blank=True)
    hod_comments = models.TextField(blank=True)
    
    management_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='management_approved_requests')
    management_approved_at = models.DateTimeField(null=True, blank=True)
    management_comments = models.TextField(blank=True)
    
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rejected_requests')
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    recalled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='recalled_requests')
    recalled_at = models.DateTimeField(null=True, blank=True)
    days_to_restore = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user} - {self.leave_type} ({self.start_date} to {self.end_date})"
    
    @property
    def is_current(self):
        """Check if leave is currently active"""
        today = timezone.now().date()
        return self.status == 'APPROVED' and self.start_date <= today <= self.end_date
    
    @property
    def is_future(self):
        """Check if leave is in the future"""
        today = timezone.now().date()
        return self.status == 'APPROVED' and self.start_date > today
    
    def can_be_recalled(self):
        """Check if leave can be recalled (approved and not fully completed)"""
        today = timezone.now().date()
        return self.status == 'APPROVED' and self.end_date >= today
    
    class Meta:
        ordering = ['-created_at']


class LeaveAllocation(models.Model):
    """Track automatic leave allocations (for annual leave accrual)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    allocation_date = models.DateField()
    days_allocated = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.CharField(max_length=200, default='Monthly accrual')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-allocation_date']
    
    def __str__(self):
        return f"{self.user} - {self.leave_type}: {self.days_allocated} days allocated on {self.allocation_date}"
