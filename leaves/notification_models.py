from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Notification(models.Model):
    """Simple in-app notification model for tracking user notifications"""
    NOTIFICATION_TYPES = [
        ('LEAVE_APPROVED', 'Leave Approved'),
        ('LEAVE_REJECTED', 'Leave Rejected'),
        ('LEAVE_HOD_APPROVED', 'Leave HOD Approved'),
        ('LEAVE_RECALLED', 'Leave Recalled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional: link to the related leave request
    leave_request = models.ForeignKey(
        'LeaveRequest', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='notifications'
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username}: {self.title}"


def create_notification(user, notification_type, title, message, leave_request=None):
    """Helper function to create notifications"""
    return Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        message=message,
        leave_request=leave_request
    )
