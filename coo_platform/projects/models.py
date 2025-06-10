"""
Project models for COO Platform.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from core.models import TimeStampedModel, UUIDModel
from tenants.models import TenantAwareModel
from tenants.middleware import TenantAwareManager
import uuid


class ProjectCategory(TenantAwareModel, TimeStampedModel):
    """
    Categories for organizing projects.
    """
    objects = TenantAwareManager()

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Project Categories"
        unique_together = ['tenant', 'name']
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Project(UUIDModel, TenantAwareModel, TimeStampedModel):
    """
    Main project model with comprehensive tracking capabilities.
    """
    # Use the tenant-aware manager
    objects = TenantAwareManager()

    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ProjectCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='projects'
    )
    
    # Status and Priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Team and Ownership
    project_manager = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='managed_projects'
    )
    team_members = models.ManyToManyField(
        User, 
        through='ProjectMembership',
        related_name='project_memberships'
    )
    
    # Timeline
    start_date = models.DateField(null=True, blank=True)
    target_end_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    
    # Budget and Resources
    budget_allocated = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Budget allocated for this project"
    )
    budget_spent = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Amount spent so far"
    )
    
    # Progress Tracking
    progress_percentage = models.PositiveIntegerField(
        default=0,
        help_text="Overall project progress (0-100)"
    )
    
    # Metadata
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    
    # Files and Documentation
    project_charter = models.FileField(upload_to='projects/charters/', blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'priority']),
            models.Index(fields=['project_manager', 'status']),
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        if self.start_date and self.target_end_date:
            if self.start_date > self.target_end_date:
                raise ValidationError('Start date cannot be after target end date.')
        
        if self.progress_percentage < 0 or self.progress_percentage > 100:
            raise ValidationError('Progress percentage must be between 0 and 100.')
    
    def save(self, *args, **kwargs):
        # Auto-complete project if progress is 100%
        if self.progress_percentage == 100 and self.status != 'completed':
            self.status = 'completed'
            if not self.actual_end_date:
                self.actual_end_date = timezone.now().date()
        
        super().save(*args, **kwargs)
    
    @property
    def is_overdue(self):
        if self.target_end_date and self.status not in ['completed', 'cancelled']:
            return timezone.now().date() > self.target_end_date
        return False
    
    @property
    def days_remaining(self):
        if self.target_end_date and self.status not in ['completed', 'cancelled']:
            delta = self.target_end_date - timezone.now().date()
            return delta.days
        return None
    
    @property
    def budget_remaining(self):
        if self.budget_allocated:
            return self.budget_allocated - self.budget_spent
        return None
    
    @property
    def budget_utilization(self):
        if self.budget_allocated and self.budget_allocated > 0:
            return (self.budget_spent / self.budget_allocated) * 100
        return 0
    
    def get_absolute_url(self):
        return reverse('projects:detail', kwargs={'pk': self.pk})
    
    def update_progress(self):
        """
        Auto-calculate progress based on completed tasks.
        """
        total_tasks = self.tasks.count()
        if total_tasks == 0:
            self.progress_percentage = 0
        else:
            completed_tasks = self.tasks.filter(status='completed').count()
            self.progress_percentage = int((completed_tasks / total_tasks) * 100)
        
        self.save(update_fields=['progress_percentage'])
    
    def get_team_members(self):
        """
        Get all team members with their roles.
        """
        return ProjectMembership.objects.filter(project=self).select_related('user')


class ProjectMembership(TimeStampedModel):
    """
    Through model for project team membership with roles.
    """
    ROLE_CHOICES = [
        ('manager', 'Project Manager'),
        ('lead', 'Team Lead'),
        ('developer', 'Developer'),
        ('designer', 'Designer'),
        ('analyst', 'Business Analyst'),
        ('tester', 'QA Tester'),
        ('stakeholder', 'Stakeholder'),
        ('observer', 'Observer'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='developer')
    is_active = models.BooleanField(default=True)
    joined_date = models.DateField(auto_now_add=True)
    
    # Permissions
    can_edit_project = models.BooleanField(default=False)
    can_manage_tasks = models.BooleanField(default=True)
    can_invite_members = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['project', 'user']
        ordering = ['role', 'user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.project.name} ({self.role})"


class Task(UUIDModel, TimeStampedModel):
    """
    Individual tasks within projects.
    """
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'Under Review'),
        ('completed', 'Completed'),
        ('blocked', 'Blocked'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Assignment and Status
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_tasks'
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='created_tasks'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Timeline
    due_date = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Estimation and Tracking
    estimated_hours = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    actual_hours = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        default=0
    )
    
    # Dependencies
    depends_on = models.ManyToManyField(
        'self', 
        symmetrical=False, 
        blank=True,
        related_name='dependents'
    )
    
    # Metadata
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['priority', 'due_date', 'created_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Auto-set timestamps based on status changes
        if self.status == 'in_progress' and not self.started_at:
            self.started_at = timezone.now()
        elif self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        
        super().save(*args, **kwargs)
        
        # Update project progress when task status changes
        if self.pk:  # Only for existing tasks
            self.project.update_progress()
    
    @property
    def is_overdue(self):
        if self.due_date and self.status != 'completed':
            return timezone.now() > self.due_date
        return False
    
    @property
    def can_start(self):
        """
        Check if task can be started (all dependencies completed).
        """
        return not self.depends_on.exclude(status='completed').exists()
    
    def get_absolute_url(self):
        return reverse('projects:task_detail', kwargs={'pk': self.pk})


class TaskComment(UUIDModel, TimeStampedModel):
    """
    Comments on tasks for collaboration.
    """
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    
    # File attachments
    attachment = models.FileField(upload_to='task_attachments/', blank=True, null=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.task.title}"


class ProjectUpdate(UUIDModel, TimeStampedModel):
    """
    Status updates and reports for projects.
    """
    UPDATE_TYPES = [
        ('status', 'Status Update'),
        ('milestone', 'Milestone'),
        ('risk', 'Risk/Issue'),
        ('budget', 'Budget Update'),
        ('resource', 'Resource Update'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='updates')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    update_type = models.CharField(max_length=20, choices=UPDATE_TYPES, default='status')
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Metrics at time of update
    progress_at_update = models.PositiveIntegerField(null=True, blank=True)
    budget_spent_at_update = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.title}"
