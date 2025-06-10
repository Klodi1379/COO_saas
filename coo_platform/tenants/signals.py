"""
Django signals for tenants app.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Tenant, TenantUser, TenantInvitation
from core.utils import create_notification, log_user_action


@receiver(post_save, sender=Tenant)
def tenant_created(sender, instance, created, **kwargs):
    """
    Handle actions when a tenant is created.
    """
    if created:
        # Set up default settings for new tenant
        default_settings = {
            'theme': 'default',
            'currency': 'USD',
            'date_format': 'MM/DD/YYYY',
            'time_zone': 'UTC',
            'email_notifications': True,
        }
        instance.settings = default_settings
        instance.save(update_fields=['settings'])


@receiver(post_save, sender=TenantUser)
def tenant_user_created(sender, instance, created, **kwargs):
    """
    Handle actions when a user joins a tenant.
    """
    if created:
        # Send welcome notification to the user
        create_notification(
            recipient=instance.user,
            notification_type='info',
            title=f'Welcome to {instance.tenant.name}!',
            message=f'You have been added to {instance.tenant.name} as a {instance.get_role_display()}.',
            action_url='/dashboard/',
            action_label='Go to Dashboard'
        )
        
        # Notify tenant admins about new user
        admins = TenantUser.objects.filter(
            tenant=instance.tenant,
            role__in=['owner', 'admin'],
            is_active=True
        ).exclude(user=instance.user)
        
        for admin in admins:
            create_notification(
                recipient=admin.user,
                notification_type='info',
                title='New team member added',
                message=f'{instance.user.get_full_name() or instance.user.username} has joined your team.',
                action_url='/tenants/settings/',
                action_label='View Team'
            )


@receiver(post_save, sender=TenantInvitation)
def invitation_created(sender, instance, created, **kwargs):
    """
    Handle actions when an invitation is created.
    """
    if created:
        # Log the invitation
        print(f"Invitation created for {instance.email} to join {instance.tenant.name}")


@receiver(post_delete, sender=TenantUser)
def tenant_user_removed(sender, instance, **kwargs):
    """
    Handle actions when a user is removed from a tenant.
    """
    # Notify the removed user
    create_notification(
        recipient=instance.user,
        notification_type='warning',
        title=f'Removed from {instance.tenant.name}',
        message=f'You have been removed from {instance.tenant.name}.',
    )
    
    # Notify tenant admins
    admins = TenantUser.objects.filter(
        tenant=instance.tenant,
        role__in=['owner', 'admin'],
        is_active=True
    )
    
    for admin in admins:
        create_notification(
            recipient=admin.user,
            notification_type='info',
            title='Team member removed',
            message=f'{instance.user.get_full_name() or instance.user.username} has been removed from your team.',
            action_url='/tenants/settings/',
            action_label='View Team'
        )
