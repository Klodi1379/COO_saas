from django import forms
from .models import Project

class ProjectForm(forms.ModelForm):
    """
    Custom form for project creation/editing with enhanced tag handling.
    """
    tags = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    budget_allocated = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    budget_spent = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    progress_percentage = forms.IntegerField(
        min_value=0,
        max_value=100,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '100',
            'step': '1'
        })
    )

    class Meta:
        model = Project
        fields = [
            'name', 'description', 'category', 'status', 'priority',
            'project_manager', 'start_date', 'target_end_date', 'actual_end_date',
            'budget_allocated', 'budget_spent', 'progress_percentage', 'tags'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter project name'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'Describe your project goals and scope'
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'project_manager': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'text',
                'placeholder': 'Select start date'
            }),
            'target_end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'text',
                'placeholder': 'Select target end date'
            }),
            'actual_end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'text',
                'placeholder': 'Select actual end date'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert tags list to comma-separated string if instance exists
        if self.instance.pk and self.instance.tags:
            self.initial['tags'] = ','.join(self.instance.tags)
        
        # Set default values for new projects
        if not self.instance.pk:
            self.fields['progress_percentage'].initial = 0
            self.fields['progress_percentage'].required = False

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        target_end_date = cleaned_data.get('target_end_date')
        actual_end_date = cleaned_data.get('actual_end_date')
        progress = cleaned_data.get('progress_percentage')
        budget_allocated = cleaned_data.get('budget_allocated')
        budget_spent = cleaned_data.get('budget_spent')

        # Date validation
        if start_date and target_end_date and start_date > target_end_date:
            raise forms.ValidationError("Start date cannot be after target end date.")
        
        if actual_end_date and start_date and actual_end_date < start_date:
            raise forms.ValidationError("Actual end date cannot be before start date.")

        # Progress validation
        if progress is not None:
            if progress < 0 or progress > 100:
                raise forms.ValidationError("Progress must be between 0 and 100.")

        # Budget validation
        if budget_allocated and budget_spent and budget_spent > budget_allocated:
            raise forms.ValidationError("Budget spent cannot exceed budget allocated.")

        return cleaned_data

    def clean_tags(self):
        tags = self.cleaned_data.get('tags', '')
        if tags:
            # Split by comma and clean each tag
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            return tag_list
        return []

    def clean_progress_percentage(self):
        progress = self.cleaned_data.get('progress_percentage')
        if progress is None:
            return 0  # Default value
        return progress
