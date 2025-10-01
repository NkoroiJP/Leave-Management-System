from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta
from decimal import Decimal

from .models import LeaveRequest, LeaveType, LeaveBalance, User, Department
from .forms import LeaveRequestForm
from .utils import (
    calculate_leave_days, can_user_request_leave, get_or_create_leave_balance,
    update_leave_balance_on_approval, update_leave_balance_on_rejection,
    update_leave_balance_on_recall
)
from .notifications import notify_leave_status


@login_required
def dashboard(request):
    """Main dashboard showing leave balances and current leave status"""
    current_year = timezone.now().year
    user = request.user
    
    # Get user's leave balances
    leave_balances = LeaveBalance.objects.filter(
        user=user,
        year=current_year
    ).select_related('leave_type')
    
    # Get pending leave requests
    pending_requests = LeaveRequest.objects.filter(
        user=user,
        status__in=['PENDING', 'HOD_APPROVED']
    ).order_by('-created_at')[:5]
    
    # Get current and upcoming approved leaves
    today = timezone.now().date()
    current_leaves = LeaveRequest.objects.filter(
        user=user,
        status='APPROVED',
        start_date__lte=today,
        end_date__gte=today
    )
    
    upcoming_leaves = LeaveRequest.objects.filter(
        user=user,
        status='APPROVED',
        start_date__gt=today
    ).order_by('start_date')[:3]
    
    # Get all users currently on leave (for the dashboard widget)
    users_on_leave = LeaveRequest.objects.filter(
        status='APPROVED',
        start_date__lte=today,
        end_date__gte=today
    ).select_related('user', 'leave_type')
    
    # For HODs and Management, get pending approvals
    pending_approvals = []
    if user.role in ['HOD', 'MANAGEMENT']:
        if user.role == 'HOD':
            # HOD sees requests from their department
            pending_approvals = LeaveRequest.objects.filter(
                user__department=user.department,
                status='PENDING'
            ).exclude(user__role='HOD')  # HODs can't approve other HODs
        elif user.role == 'MANAGEMENT':
            # Management sees all HOD_APPROVED requests and HOD requests
            pending_approvals = LeaveRequest.objects.filter(
                Q(status='HOD_APPROVED') | 
                Q(status='PENDING', user__role='HOD')
            )
    
    context = {
        'leave_balances': leave_balances,
        'pending_requests': pending_requests,
        'current_leaves': current_leaves,
        'upcoming_leaves': upcoming_leaves,
        'users_on_leave': users_on_leave,
        'pending_approvals': pending_approvals,
    }
    
    return render(request, 'leaves/dashboard.html', context)


@login_required
def request_leave(request):
    """View to create a new leave request"""
    # Check if user is eligible for leave
    if not request.user.is_eligible_for_leave():
        probation_end_date = request.user.get_probation_end_date()
        messages.error(request, f'You are not eligible to request leave until {probation_end_date.strftime("%B %d, %Y")} (6 months from hire date).')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.user = request.user
            
            # Calculate days requested
            days_requested = calculate_leave_days(
                leave_request.start_date,
                leave_request.end_date,
                leave_request.leave_type
            )
            leave_request.days_requested = Decimal(str(days_requested))
            
            # Check if user can request this leave
            can_request, reason = can_user_request_leave(
                request.user,
                leave_request.leave_type,
                leave_request.start_date,
                leave_request.end_date
            )
            
            if not can_request:
                messages.error(request, f"Cannot request leave: {reason}")
                return render(request, 'leaves/request_leave.html', {'form': form})
            
            # Update balance to reserve the days
            balance = get_or_create_leave_balance(
                request.user,
                leave_request.leave_type,
                leave_request.start_date.year
            )
            balance.pending_days += leave_request.days_requested
            balance.save()
            
            leave_request.save()
            
            messages.success(request, 'Leave request submitted successfully!')
            return redirect('dashboard')
    else:
        form = LeaveRequestForm()
    
    return render(request, 'leaves/request_leave.html', {'form': form})


class LeaveRequestListView(LoginRequiredMixin, ListView):
    """List all leave requests for the current user"""
    model = LeaveRequest
    template_name = 'leaves/leave_request_list.html'
    context_object_name = 'leave_requests'
    paginate_by = 10
    
    def get_queryset(self):
        return LeaveRequest.objects.filter(user=self.request.user).order_by('-created_at')


class LeaveRequestDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a leave request"""
    model = LeaveRequest
    template_name = 'leaves/leave_request_detail.html'
    context_object_name = 'leave_request'
    
    def get_queryset(self):
        # Users can only view their own requests unless they're HOD/Management
        user = self.request.user
        if user.role == 'MANAGEMENT':
            return LeaveRequest.objects.all()
        elif user.role == 'HOD':
            return LeaveRequest.objects.filter(
                Q(user=user) | Q(user__department=user.department)
            )
        else:
            return LeaveRequest.objects.filter(user=user)


@login_required
def approval_dashboard(request):
    """Dashboard for HODs and Management to approve leave requests"""
    user = request.user
    
    if user.role not in ['HOD', 'MANAGEMENT']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    # Get pending requests based on user role
    if user.role == 'HOD':
        pending_requests = LeaveRequest.objects.filter(
            user__department=user.department,
            status='PENDING'
        ).exclude(user__role='HOD')  # HODs can't approve other HODs
    else:  # MANAGEMENT
        pending_requests = LeaveRequest.objects.filter(
            Q(status='HOD_APPROVED') | 
            Q(status='PENDING', user__role='HOD')
        )
    
    pending_requests = pending_requests.select_related('user', 'leave_type').order_by('-created_at')
    
    context = {
        'pending_requests': pending_requests,
        'user_role': user.role,
    }
    
    return render(request, 'leaves/approval_dashboard.html', context)


@login_required
@require_POST
def approve_leave(request, leave_request_id):
    """Approve a leave request"""
    leave_request = get_object_or_404(LeaveRequest, id=leave_request_id)
    user = request.user
    
    # Check permissions
    if not user.can_approve_leave(leave_request):
        messages.error(request, 'You do not have permission to approve this leave request.')
        return redirect('approval_dashboard')
    
    comments = request.POST.get('comments', '')
    
    # Determine approval level
    if user.role == 'HOD' and leave_request.status == 'PENDING':
        # First level approval by HOD
        leave_request.status = 'HOD_APPROVED'
        leave_request.hod_approved_by = user
        leave_request.hod_approved_at = timezone.now()
        leave_request.hod_comments = comments
        leave_request.save()
        
        # Send notification
        notify_leave_status(leave_request)
        
        messages.success(request, f'Leave request approved at HOD level. Forwarded to Management.')
        
    elif user.role == 'MANAGEMENT':
        # Final approval by Management
        leave_request.status = 'APPROVED'
        leave_request.management_approved_by = user
        leave_request.management_approved_at = timezone.now()
        leave_request.management_comments = comments
        
        # Update leave balance
        update_leave_balance_on_approval(leave_request)
        
        leave_request.save()
        
        # Send notification
        notify_leave_status(leave_request)
        
        messages.success(request, f'Leave request fully approved.')
    
    return redirect('approval_dashboard')


@login_required
@require_POST
def reject_leave(request, leave_request_id):
    """Reject a leave request"""
    leave_request = get_object_or_404(LeaveRequest, id=leave_request_id)
    user = request.user
    
    # Check permissions
    if not user.can_approve_leave(leave_request):
        messages.error(request, 'You do not have permission to reject this leave request.')
        return redirect('approval_dashboard')
    
    rejection_reason = request.POST.get('rejection_reason', '')
    
    if not rejection_reason:
        messages.error(request, 'Rejection reason is required.')
        return redirect('approval_dashboard')
    
    leave_request.status = 'REJECTED'
    leave_request.rejected_by = user
    leave_request.rejected_at = timezone.now()
    leave_request.rejection_reason = rejection_reason
    
    # Update leave balance
    update_leave_balance_on_rejection(leave_request)
    
    leave_request.save()
    
    # Send notification
    notify_leave_status(leave_request)
    
    messages.success(request, 'Leave request rejected.')
    return redirect('approval_dashboard')


@login_required
@require_POST
def recall_leave(request, leave_request_id):
    """Recall an approved leave (Management only)"""
    leave_request = get_object_or_404(LeaveRequest, id=leave_request_id)
    user = request.user
    
    # Only management can recall leaves
    if user.role != 'MANAGEMENT':
        messages.error(request, 'Only management can recall approved leaves.')
        return redirect('dashboard')
    
    # Check if leave can be recalled
    if not leave_request.can_be_recalled():
        messages.error(request, 'This leave cannot be recalled (either not approved or already completed).')
        return redirect('dashboard')
    
    # Calculate days to restore
    today = timezone.now().date()
    if leave_request.start_date > today:
        # Leave hasn't started yet, restore all days
        days_to_restore = leave_request.days_requested
    else:
        # Leave has started, calculate remaining days
        remaining_days = calculate_leave_days(
            max(today, leave_request.start_date),
            leave_request.end_date,
            leave_request.leave_type
        )
        days_to_restore = Decimal(str(remaining_days))
    
    leave_request.status = 'RECALLED'
    leave_request.recalled_by = user
    leave_request.recalled_at = timezone.now()
    leave_request.days_to_restore = days_to_restore
    
    # Update leave balance
    update_leave_balance_on_recall(leave_request, days_to_restore)
    
    leave_request.save()
    
    messages.success(request, f'Leave recalled successfully. {days_to_restore} days restored to balance.')
    return redirect('dashboard')


@login_required
def who_is_on_leave(request):
    """View showing all users currently on leave"""
    today = timezone.now().date()
    
    # Get all users currently on leave
    current_leaves = LeaveRequest.objects.filter(
        status='APPROVED',
        start_date__lte=today,
        end_date__gte=today
    ).select_related('user', 'leave_type', 'user__department').order_by('user__last_name')
    
    # Get upcoming leaves (starting in next 7 days)
    upcoming_leaves = LeaveRequest.objects.filter(
        status='APPROVED',
        start_date__gt=today,
        start_date__lte=today + timedelta(days=7)
    ).select_related('user', 'leave_type', 'user__department').order_by('start_date')
    
    context = {
        'current_leaves': current_leaves,
        'upcoming_leaves': upcoming_leaves,
        'today': today,
    }
    
    return render(request, 'leaves/who_is_on_leave.html', context)


@login_required
def leave_balance_view(request):
    """View showing user's leave balances"""
    current_year = timezone.now().year
    
    leave_balances = LeaveBalance.objects.filter(
        user=request.user,
        year=current_year
    ).select_related('leave_type').order_by('leave_type__name')
    
    context = {
        'leave_balances': leave_balances,
        'current_year': current_year,
    }
    
    return render(request, 'leaves/leave_balance.html', context)


@login_required
def calculate_days_ajax(request):
    """AJAX endpoint to calculate leave days"""
    if request.method == 'GET':
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        leave_type_id = request.GET.get('leave_type_id')
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            leave_type = LeaveType.objects.get(id=leave_type_id)
            
            days = calculate_leave_days(start_date, end_date, leave_type)
            
            return JsonResponse({
                'success': True,
                'days': days,
                'counting_type': leave_type.get_counting_type_display()
            })
            
        except (ValueError, LeaveType.DoesNotExist) as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
