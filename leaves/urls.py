from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Leave requests
    path('request/', views.request_leave, name='request_leave'),
    path('requests/', views.LeaveRequestListView.as_view(), name='leave_request_list'),
    path('requests/<int:pk>/', views.LeaveRequestDetailView.as_view(), name='leave_request_detail'),
    
    # Approval workflow
    path('approvals/', views.approval_dashboard, name='approval_dashboard'),
    path('approve/<int:leave_request_id>/', views.approve_leave, name='approve_leave'),
    path('reject/<int:leave_request_id>/', views.reject_leave, name='reject_leave'),
    path('recall/<int:leave_request_id>/', views.recall_leave, name='recall_leave'),
    
    # Information views
    path('who-is-on-leave/', views.who_is_on_leave, name='who_is_on_leave'),
    path('leave-balance/', views.leave_balance_view, name='leave_balance'),
    
    # AJAX endpoints
    path('ajax/calculate-days/', views.calculate_days_ajax, name='calculate_days_ajax'),
]
