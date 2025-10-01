from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.conf import settings


def notify_leave_status(leave_request):
    """Notify employee and HOD (and management if needed) about approval/rejection."""
    user = leave_request.user
    subject = None
    message = None

    # Build a link to the request detail (optional if auth required)
    try:
        detail_url = reverse('leave_request_detail', args=[leave_request.pk])
    except Exception:
        detail_url = '#'

    base = (
        f"Leave Type: {leave_request.leave_type.name}\n"
        f"Dates: {leave_request.start_date} to {leave_request.end_date}\n"
        f"Days: {leave_request.days_requested}\n"
        f"Status: {leave_request.get_status_display()}\n"
        f"Requested by: {user.get_full_name() or user.username}\n"
        f"Details: {detail_url}\n"
    )

    if leave_request.status == 'APPROVED':
        subject = 'Leave Request Approved'
        message = base
        if leave_request.management_comments:
            message += f"\nManagement comments: {leave_request.management_comments}\n"
    elif leave_request.status == 'REJECTED':
        subject = 'Leave Request Rejected'
        message = base
        if leave_request.rejection_reason:
            message += f"\nRejection reason: {leave_request.rejection_reason}\n"
    elif leave_request.status == 'HOD_APPROVED':
        subject = 'Leave Request HOD Approval'
        message = base
        if leave_request.hod_comments:
            message += f"\nHOD comments: {leave_request.hod_comments}\n"
    else:
        return  # no-op for other statuses

    recipients = []

    # Employee always gets notified
    if user.email:
        recipients.append(user.email)

    # HOD for the user's department
    hod_email = None
    if user.department:
        hod = user.department.user_set.filter(role='HOD').first()
        if hod and hod.email:
            hod_email = hod.email
            recipients.append(hod_email)

    # Ensure unique recipients
    recipients = list(dict.fromkeys([r for r in recipients if r]))

    if not recipients:
        return

    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@leave-system.local'),
        recipient_list=recipients,
        fail_silently=True,
    )

