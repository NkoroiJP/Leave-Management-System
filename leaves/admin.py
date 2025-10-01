from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import Department, User, LeaveType, LeaveBalance, LeaveRequest, LeaveAllocation
from .utils import initialize_user_leave_balances, setup_default_leave_types
from .tasks import initialize_new_user_leave_balances

User = get_user_model()


class CustomUserAdmin(BaseUserAdmin):
    # Fields to be displayed in the user list
    list_display = ('username', 'email', 'first_name', 'last_name', 'department', 'role', 'gender', 'employee_id', 'is_staff', 'is_active')
    list_filter = ('role', 'department', 'gender', 'is_staff', 'is_active', 'hire_date')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'employee_id')
    
    # Fields to be displayed in the user detail view
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Employee Information', {
            'fields': ('role', 'department', 'employee_id', 'hire_date', 'gender', 'phone', 'address')
        }),
        ('Leave Management', {
            'fields': ('manual_annual_leave_balance', 'probation_end_date'),
            'classes': ('collapse',),
            'description': 'Override automatic leave calculations if needed'
        }),
    )
    
    # Fields to be displayed in the add user form
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Employee Information', {
            'fields': ('role', 'department', 'employee_id', 'hire_date', 'gender', 'phone', 'address')
        }),
        ('Leave Management', {
            'fields': ('manual_annual_leave_balance', 'probation_end_date'),
            'classes': ('collapse',),
        }),
    )
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Initialize leave balances for new users
        if not change:  # This is a new user
            initialize_new_user_leave_balances.delay(obj.id)
    
    def has_add_permission(self, request):
        # Only management users can add new users
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'MANAGEMENT')
    
    def has_change_permission(self, request, obj=None):
        # Management can change anyone, HODs can change their department employees
        if request.user.is_superuser:
            return True
        if hasattr(request.user, 'role'):
            if request.user.role == 'MANAGEMENT':
                return True
            if request.user.role == 'HOD' and obj and obj.department == request.user.department:
                return True
        return False


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_days_per_year', 'is_accrual', 'accrual_rate', 'counting_type', 'is_active')
    list_filter = ('is_accrual', 'counting_type', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_by', 'created_at')
    
    def save_model(self, request, obj, form, change):
        if not change:  # This is a new leave type
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        # Only management users can add new leave types
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'MANAGEMENT')
    
    def has_change_permission(self, request, obj=None):
        # Only management users can change leave types
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'MANAGEMENT')


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'leave_type', 'year', 'allocated_days', 'used_days', 'pending_days', 'available_days')
    list_filter = ('leave_type', 'year')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('available_days', 'last_updated')
    
    def has_add_permission(self, request):
        # Only management users can manually add leave balances
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'MANAGEMENT')


class LeaveRequestStatusFilter(admin.SimpleListFilter):
    title = 'Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return [
            ('pending_approval', 'Pending Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('current', 'Currently on Leave'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'pending_approval':
            return queryset.filter(status__in=['PENDING', 'HOD_APPROVED'])
        if self.value() == 'approved':
            return queryset.filter(status='APPROVED')
        if self.value() == 'rejected':
            return queryset.filter(status='REJECTED')
        if self.value() == 'current':
            from django.utils import timezone
            today = timezone.now().date()
            return queryset.filter(status='APPROVED', start_date__lte=today, end_date__gte=today)
        return queryset


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'leave_type', 'start_date', 'end_date', 'days_requested', 'status', 'created_at')
    list_filter = (LeaveRequestStatusFilter, 'leave_type', 'start_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'reason')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'role'):
            if request.user.role == 'MANAGEMENT':
                return qs
            if request.user.role == 'HOD':
                # HODs can see requests from their department
                return qs.filter(user__department=request.user.department)
        # Regular users can only see their own requests
        return qs.filter(user=request.user)


@admin.register(LeaveAllocation)
class LeaveAllocationAdmin(admin.ModelAdmin):
    list_display = ('user', 'leave_type', 'allocation_date', 'days_allocated', 'reason')
    list_filter = ('leave_type', 'allocation_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at',)
    
    def has_add_permission(self, request):
        # Only management users can manually add allocations
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'MANAGEMENT')


# Register the custom user admin
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, CustomUserAdmin)

# Admin site customization
admin.site.site_header = "Leave Management System"
admin.site.site_title = "Leave Management"
admin.site.index_title = "Welcome to Leave Management System"

# Create default leave types on admin startup
try:
    setup_default_leave_types()
except Exception:
    pass  # Ignore errors during migrations
