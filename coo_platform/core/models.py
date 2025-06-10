"""
Core models for COO Platform.
These are the foundational models that other apps will inherit from or reference.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid


class TimeStampedModel(models.Model):
    """
    Abstract base model that provides created_at and updated_at fields.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """
    Abstract base model that provides UUID primary key.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class Meta:
        abstract = True


class UserProfile(TimeStampedModel):
    """
    Extended user profile with role and tenant information.
    """
    ROLE_CHOICES = [
        ('consultant', 'Consultant'),
        ('client_admin', 'Client Administrator'),
        ('client_user', 'Client User'),
        ('system_admin', 'System Administrator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client_user')
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    # Subscription and billing
    subscription_tier = models.CharField(max_length=20, default='basic')
    subscription_active = models.BooleanField(default=True)
    subscription_expires = models.DateTimeField(null=True, blank=True)
    
    # Platform preferences
    timezone = models.CharField(max_length=50, default='UTC')
    email_notifications = models.BooleanField(default=True)
    dashboard_layout = models.JSONField(default=dict)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"
    
    @property
    def is_consultant(self):
        return self.role == 'consultant'
    
    @property
    def is_client_admin(self):
        return self.role == 'client_admin'
    
    @property
    def can_manage_tenant(self):
        return self.role in ['consultant', 'client_admin', 'system_admin']


class AuditLog(TimeStampedModel):
    """
    Audit log for tracking important actions across the platform.
    """
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('view', 'View'),
        ('export', 'Export'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    content_type = models.CharField(max_length=100)  # Model name
    object_id = models.CharField(max_length=100)     # Object identifier
    object_repr = models.CharField(max_length=200)   # String representation
    change_message = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['content_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user} {self.action} {self.content_type} at {self.created_at}"


class Notification(TimeStampedModel):
    """
    In-app notifications for users.
    """
    NOTIFICATION_TYPES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('task_assigned', 'Task Assigned'),
        ('task_completed', 'Task Completed'),
        ('kpi_alert', 'KPI Alert'),
        ('deadline_approaching', 'Deadline Approaching'),
        ('system', 'System Notification'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Action links
    action_url = models.URLField(blank=True)
    action_label = models.CharField(max_length=50, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'created_at']),
        ]
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username}"


class SystemSetting(TimeStampedModel):
    """
    System-wide configuration settings.
    """
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)  # Can be accessed by clients
    
    def __str__(self):
        return self.key
    
    @classmethod
    def get_setting(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_setting(cls, key, value, description=''):
        setting, created = cls.objects.get_or_create(
            key=key,
            defaults={'value': value, 'description': description}
        )
        if not created:
            setting.value = value
            setting.description = description
            setting.save()
        return setting
