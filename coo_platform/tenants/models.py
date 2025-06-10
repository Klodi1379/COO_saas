"""
Tenant models for multi-tenant architecture.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from core.models import TimeStampedModel, UUIDModel
import uuid


class Tenant(UUIDModel, TimeStampedModel):
    """
    Represents a client organization (tenant) in the multi-tenant system.
    """
    SUBSCRIPTION_TIERS = [
        ('basic', 'Basic'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('trial', 'Trial'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200, help_text="Company/Organization name")
    slug = models.SlugField(unique=True, max_length=100, help_text="URL-friendly identifier")
    domain = models.CharField(max_length=100, blank=True, help_text="Custom domain (optional)")
    
    # Contact Information
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    
    # Subscription and Billing
    subscription_tier = models.CharField(max_length=20, choices=SUBSCRIPTION_TIERS, default='basic')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_starts_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)
    
    # Billing Information
    billing_email = models.EmailField(blank=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    
    # Configuration
    settings = models.JSONField(default=dict, help_text="Tenant-specific settings")
    features = models.JSONField(default=list, help_text="Enabled features for this tenant")
    
    # Limits and Usage
    max_users = models.PositiveIntegerField(default=3)
    max_projects = models.PositiveIntegerField(default=5)
    max_storage_mb = models.PositiveIntegerField(default=100)  # MB
    
    # Branding (for enterprise clients)
    logo = models.ImageField(upload_to='tenant_logos/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code")
    secondary_color = models.CharField(max_length=7, default='#6c757d', help_text="Hex color code")
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', 'subscription_tier']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def clean(self):
        if self.domain and Tenant.objects.filter(domain=self.domain).exclude(id=self.id).exists():
            raise ValidationError({'domain': 'This domain is already in use.'})
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def is_trial(self):
        return self.status == 'trial'
    
    @property
    def user_count(self):
        return self.users.count()
    
    @property
    def project_count(self):
        return self.projects.count() if hasattr(self, 'projects') else 0
    
    def can_add_user(self):
        return self.user_count < self.max_users
    
    def can_add_project(self):
        return self.project_count < self.max_projects
    
    def get_available_features(self):
        """Get features available for this tenant's subscription tier."""
        from django.conf import settings
        tier_features = settings.COO_PLATFORM_SETTINGS['FEATURES_PER_TIER'].get(
            self.subscription_tier, []
        )
        
        # Combine tier features with custom features
        all_features = set(tier_features + self.features)
        return list(all_features)
    
    def has_feature(self, feature_name):
        """Check if tenant has access to a specific feature."""
        return feature_name in self.get_available_features()


class TenantUser(TimeStampedModel):
    """
    Relationship between users and tenants with role information.
    """
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('user', 'User'),
        ('viewer', 'Viewer'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='tenant_users')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    is_active = models.BooleanField(default=True)
    
    # Permissions
    can_invite_users = models.BooleanField(default=False)
    can_manage_projects = models.BooleanField(default=False)
    can_manage_kpis = models.BooleanField(default=False)
    can_view_analytics = models.BooleanField(default=True)
    can_export_data = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['tenant', 'user']
        ordering = ['role', 'user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.tenant.name} ({self.role})"
    
    def save(self, *args, **kwargs):
        # Set default permissions based on role
        if self.role in ['owner', 'admin']:
            self.can_invite_users = True
            self.can_manage_projects = True
            self.can_manage_kpis = True
            self.can_view_analytics = True
            self.can_export_data = True
        elif self.role == 'manager':
            self.can_manage_projects = True
            self.can_manage_kpis = True
            self.can_view_analytics = True
        elif self.role == 'user':
            self.can_view_analytics = True
        
        super().save(*args, **kwargs)


class TenantInvitation(UUIDModel, TimeStampedModel):
    """
    Invitations to join a tenant.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=TenantUser.ROLE_CHOICES, default='user')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Status
    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    # Token for secure acceptance
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    
    class Meta:
        unique_together = ['tenant', 'email']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invitation for {self.email} to {self.tenant.name}"
    
    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def can_be_accepted(self):
        return not self.is_accepted and not self.is_expired


class TenantAwareModel(models.Model):
    """
    Abstract base model for all tenant-aware models.
    All models that store tenant-specific data should inherit from this.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        # Ensure tenant is set (this should be handled by middleware/views)
        if not self.tenant_id:
            raise ValueError("Tenant must be specified for tenant-aware models")
        super().save(*args, **kwargs)


# Proxy models for easier admin management
class ActiveTenant(Tenant):
    class Meta:
        proxy = True
        verbose_name = "Active Tenant"
        verbose_name_plural = "Active Tenants"


class TrialTenant(Tenant):
    class Meta:
        proxy = True
        verbose_name = "Trial Tenant"
        verbose_name_plural = "Trial Tenants"
