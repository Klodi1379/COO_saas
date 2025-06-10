"""
Utility functions for tenant management.
"""
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from .models import Tenant, TenantUser, TenantInvitation
import uuid
from datetime import timedelta


def get_tenant_from_request(request):
    """
    Extract tenant information from request.
    """
    return getattr(request, 'tenant', None)


def create_tenant(name, contact_email, subscription_tier='basic', owner_user=None):
    """
    Create a new tenant with an owner.
    
    Args:
        name: Tenant name
        contact_email: Contact email
        subscription_tier: Subscription tier
        owner_user: User object to be the owner (optional)
    
    Returns:
        tuple: (tenant, tenant_user) or (tenant, None)
    """
    from django.utils.text import slugify
    
    # Create tenant
    tenant = Tenant.objects.create(
        name=name,
        contact_email=contact_email,
        subscription_tier=subscription_tier,
        status='trial',
        trial_ends_at=timezone.now() + timedelta(days=14),  # 14-day trial
    )
    
    # Create owner relationship if user provided
    tenant_user = None
    if owner_user:
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=owner_user,
            role='owner',
            is_active=True,
            can_invite_users=True,
            can_manage_projects=True,
            can_manage_kpis=True,
            can_view_analytics=True,
            can_export_data=True,
        )
    
    return tenant, tenant_user


def invite_user_to_tenant(tenant, email, role, invited_by, send_email=True):
    """
    Invite a user to join a tenant.
    
    Args:
        tenant: Tenant object
        email: Email of user to invite
        role: Role for the user
        invited_by: User object of who is sending the invitation
        send_email: Whether to send invitation email
    
    Returns:
        TenantInvitation object
    """
    # Check if user is already a member
    existing_user = User.objects.filter(email=email).first()
    if existing_user and TenantUser.objects.filter(tenant=tenant, user=existing_user).exists():
        raise ValueError("User is already a member of this tenant")
    
    # Check if there's already a pending invitation
    existing_invitation = TenantInvitation.objects.filter(
        tenant=tenant,
        email=email,
        is_accepted=False
    ).first()
    
    if existing_invitation and not existing_invitation.is_expired:
        raise ValueError("User already has a pending invitation")
    
    # Create invitation
    invitation = TenantInvitation.objects.create(
        tenant=tenant,
        email=email,
        role=role,
        invited_by=invited_by,
        expires_at=timezone.now() + timedelta(days=7)  # 7-day expiry
    )
    
    if send_email:
        send_invitation_email(invitation)
    
    return invitation


def send_invitation_email(invitation):
    """
    Send invitation email to user.
    """
    accept_url = f"{settings.SITE_URL}{reverse('tenants:accept_invitation', kwargs={'token': invitation.token})}"
    
    subject = f"Invitation to join {invitation.tenant.name}"
    message = f"""
    You've been invited to join {invitation.tenant.name} on COO Platform.
    
    Role: {invitation.get_role_display()}
    Invited by: {invitation.invited_by.get_full_name() or invitation.invited_by.username}
    
    Click the link below to accept this invitation:
    {accept_url}
    
    This invitation expires on {invitation.expires_at.strftime('%B %d, %Y at %I:%M %p')}.
    
    If you don't have an account, you'll be prompted to create one.
    """
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=False
    )


def accept_invitation(invitation, user=None):
    """
    Accept a tenant invitation.
    
    Args:
        invitation: TenantInvitation object
        user: User object (if None, will try to find by email)
    
    Returns:
        TenantUser object
    """
    if invitation.is_accepted:
        raise ValueError("Invitation already accepted")
    
    if invitation.is_expired:
        raise ValueError("Invitation has expired")
    
    # Find or get user
    if not user:
        try:
            user = User.objects.get(email=invitation.email)
        except User.DoesNotExist:
            raise ValueError("User account not found. Please create an account first.")
    
    # Create tenant user relationship
    tenant_user = TenantUser.objects.create(
        tenant=invitation.tenant,
        user=user,
        role=invitation.role,
        is_active=True
    )
    
    # Mark invitation as accepted
    invitation.is_accepted = True
    invitation.accepted_at = timezone.now()
    invitation.save()
    
    return tenant_user


def switch_user_tenant(user, tenant):
    """
    Switch user's active tenant.
    
    Args:
        user: User object
        tenant: Tenant object
    
    Returns:
        bool: Success status
    """
    # Verify user has access to this tenant
    tenant_user = TenantUser.objects.filter(
        user=user,
        tenant=tenant,
        is_active=True
    ).first()
    
    if not tenant_user:
        return False
    
    # Update user's profile with current tenant
    if hasattr(user, 'profile'):
        user.profile.current_tenant = tenant
        user.profile.save()
    
    return True


def get_user_tenants(user):
    """
    Get all tenants user has access to.
    
    Args:
        user: User object
    
    Returns:
        QuerySet of Tenant objects
    """
    if hasattr(user, 'profile') and user.profile.is_consultant:
        # Consultants can access all active tenants
        return Tenant.objects.filter(status__in=['active', 'trial'])
    
    # Regular users can only access tenants they're members of
    tenant_ids = TenantUser.objects.filter(
        user=user,
        is_active=True
    ).values_list('tenant_id', flat=True)
    
    return Tenant.objects.filter(id__in=tenant_ids)


def check_tenant_limits(tenant):
    """
    Check if tenant is within their subscription limits.
    
    Args:
        tenant: Tenant object
    
    Returns:
        dict: Status of various limits
    """
    return {
        'users': {
            'current': tenant.user_count,
            'limit': tenant.max_users,
            'can_add': tenant.can_add_user(),
        },
        'projects': {
            'current': tenant.project_count,
            'limit': tenant.max_projects,
            'can_add': tenant.can_add_project(),
        },
        'storage': {
            'current': 0,  # TODO: Calculate actual storage usage
            'limit': tenant.max_storage_mb,
            'can_add': True,  # TODO: Implement storage checking
        }
    }


def upgrade_tenant_subscription(tenant, new_tier):
    """
    Upgrade tenant subscription tier.
    
    Args:
        tenant: Tenant object
        new_tier: New subscription tier
    
    Returns:
        bool: Success status
    """
    from django.conf import settings
    
    tier_settings = settings.COO_PLATFORM_SETTINGS
    
    if new_tier not in dict(Tenant.SUBSCRIPTION_TIERS):
        return False
    
    # Update tenant limits based on new tier
    limits = tier_settings['MAX_USERS_PER_TIER'].get(new_tier, 3)
    project_limits = tier_settings['MAX_PROJECTS_PER_TIER'].get(new_tier, 5)
    
    tenant.subscription_tier = new_tier
    tenant.max_users = limits
    tenant.max_projects = project_limits
    tenant.status = 'active'
    
    # Update features
    features = tier_settings['FEATURES_PER_TIER'].get(new_tier, [])
    tenant.features = features
    
    tenant.save()
    
    return True


def deactivate_tenant(tenant, reason=''):
    """
    Deactivate a tenant.
    
    Args:
        tenant: Tenant object
        reason: Reason for deactivation
    """
    tenant.status = 'suspended'
    tenant.save()
    
    # TODO: Send notification to tenant users
    # TODO: Log the deactivation
