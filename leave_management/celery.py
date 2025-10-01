import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leave_management.settings')

app = Celery('leave_management')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    'monthly-leave-accrual': {
        'task': 'leaves.tasks.monthly_leave_accrual',
        'schedule': 30.0,  # Run every 30 seconds for testing, change to monthly in production
        # For monthly: 'schedule': crontab(day_of_month=1, hour=0, minute=0),
    },
}

app.conf.timezone = 'UTC'


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
