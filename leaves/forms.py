from django import forms
from django.utils import timezone
from .models import LeaveRequest, LeaveType


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat()
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat()
            }),
            'leave_type': forms.Select(attrs={'class': 'form-control'}),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Please provide reason for leave request...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active leave types
        self.fields['leave_type'].queryset = LeaveType.objects.filter(is_active=True)
        
        # Make all fields required
        for field in self.fields.values():
            field.required = True
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise forms.ValidationError("End date must be after start date.")
            
            if start_date < timezone.now().date():
                raise forms.ValidationError("Start date cannot be in the past.")
        
        return cleaned_data


class ApprovalForm(forms.Form):
    """Form for approving/rejecting leave requests"""
    action = forms.ChoiceField(choices=[
        ('approve', 'Approve'),
        ('reject', 'Reject')
    ], widget=forms.RadioSelect)
    
    comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional comments...'
        })
    )
    
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Please provide reason for rejection...'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        if action == 'reject' and not rejection_reason:
            raise forms.ValidationError("Rejection reason is required when rejecting a request.")
        
        return cleaned_data


class RecallForm(forms.Form):
    """Form for recalling approved leave"""
    recall_reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Please provide reason for recalling this leave...'
        })
    )
