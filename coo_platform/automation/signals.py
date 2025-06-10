"""
Django signals for automation app.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import AutomationRule, AutomationAction, AutomationSchedule
from core.utils import create_notification


@receiver(post_save, sender=AutomationRule)
def automation_rule_created(sender, instance, created, **kwargs):
    """
    Handle actions when an automation rule is created or updated.
    """
    if created:
        # Notify the creator
        create_notification(
            recipient=instance.created_by,
            notification_type='info',
            title='Automation rule created',
            message=f'Your automation rule "{instance.name}" has been created and is ready to be configured.',
            action_url=f'/automation/{instance.id}/',
            action_label='Configure Rule'
        )
    
    # Auto-create schedule for time-based triggers
    elif instance.trigger_type == 'time_based' and not hasattr(instance, 'schedule'):
        from datetime import datetime, time
        
        # Create a default schedule
        AutomationSchedule.objects.create(
            rule=instance,
            frequency='daily',
            start_time=time(9, 0),  # 9 AM default
            start_date=datetime.now().date(),
            next_run=datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        )


@receiver(post_save, sender=AutomationAction)
def automation_action_created(sender, instance, created, **kwargs):
    """
    Handle actions when an automation action is created.
    """
    if created:
        # Notify rule owner if different from action creator
        if hasattr(instance.rule, 'created_by') and instance.rule.created_by:
            create_notification(
                recipient=instance.rule.created_by,
                notification_type='info',
                title='New automation action added',
                message=f'A new action "{instance.name}" has been added to your automation rule "{instance.rule.name}".',
                action_url=f'/automation/{instance.rule.id}/',
                action_label='View Rule'
            )


@receiver(post_delete, sender=AutomationRule)
def automation_rule_deleted(sender, instance, **kwargs):
    """
    Handle cleanup when an automation rule is deleted.
    """
    # Notify team members who had access
    for user in instance.team_access.all():
        create_notification(
            recipient=user,
            notification_type='warning',
            title='Automation rule deleted',
            message=f'The automation rule "{instance.name}" has been deleted.',
        )


@receiver(post_save, sender=AutomationSchedule)
def schedule_updated(sender, instance, **kwargs):
    """
    Handle schedule updates.
    """
    # Recalculate next run time when schedule is updated
    if not kwargs.get('created', False):  # Only for updates, not creation
        instance.calculate_next_run()
