"""
Django signals for core app.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, AuditLog
from .utils import create_notification


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create a UserProfile when a User is created.
    """
    if created:
        UserProfile.objects.create(
            user=instance,
            role='client_user'  # Default role
        )
        
        # Send welcome notification
        create_notification(
            recipient=instance,
            notification_type='info',
            title='Welcome to COO Platform!',
            message='Your account has been created successfully. Start by exploring the dashboard.',
            action_url='/dashboard/',
            action_label='Go to Dashboard'
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Save the UserProfile when the User is saved.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """
    Log when a user is deleted.
    """
    AuditLog.objects.create(
        user=None,  # System action
        action='delete',
        content_type='User',
        object_id=str(instance.id),
        object_repr=str(instance),
        change_message=f'User {instance.username} was deleted'
    )
