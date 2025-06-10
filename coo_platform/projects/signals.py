"""
Django signals for projects app.
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Project, Task, ProjectMembership
from core.utils import create_notification


@receiver(post_save, sender=Project)
def project_created(sender, instance, created, **kwargs):
    """
    Handle actions when a project is created.
    """
    if created:
        # Create initial project update
        from .models import ProjectUpdate
        ProjectUpdate.objects.create(
            project=instance,
            author=instance.project_manager or instance.tenant.tenant_users.filter(
                role='owner'
            ).first().user,
            update_type='status',
            title='Project Created',
            content=f'Project "{instance.name}" has been created and is ready to begin.',
            progress_at_update=0,
            budget_spent_at_update=0
        )


@receiver(post_save, sender=Task)
def task_status_changed(sender, instance, **kwargs):
    """
    Handle task status changes and notifications.
    """
    # Only process if this is an update, not creation
    if instance.pk:
        try:
            old_instance = Task.objects.get(pk=instance.pk)
        except Task.DoesNotExist:
            return
        
        # If status changed to completed
        if old_instance.status != 'completed' and instance.status == 'completed':
            # Notify project manager
            if instance.project.project_manager:
                create_notification(
                    recipient=instance.project.project_manager,
                    notification_type='task_completed',
                    title='Task completed',
                    message=f'Task "{instance.title}" has been completed by {instance.assigned_to or "someone"}.',
                    action_url=instance.project.get_absolute_url(),
                    action_label='View Project'
                )
            
            # Notify other team members if configured
            # TODO: Add notification preferences


@receiver(post_save, sender=ProjectMembership)
def project_member_added(sender, instance, created, **kwargs):
    """
    Handle when a user is added to a project.
    """
    if created:
        # Notify the user about being added to the project
        create_notification(
            recipient=instance.user,
            notification_type='info',
            title=f'Added to project: {instance.project.name}',
            message=f'You have been added to the project "{instance.project.name}" as a {instance.get_role_display()}.',
            action_url=instance.project.get_absolute_url(),
            action_label='View Project'
        )
        
        # Notify project manager about new team member
        if instance.project.project_manager and instance.project.project_manager != instance.user:
            create_notification(
                recipient=instance.project.project_manager,
                notification_type='info',
                title='New team member added',
                message=f'{instance.user.get_full_name() or instance.user.username} has been added to "{instance.project.name}".',
                action_url=instance.project.get_absolute_url(),
                action_label='View Project'
            )


@receiver(post_delete, sender=ProjectMembership)
def project_member_removed(sender, instance, **kwargs):
    """
    Handle when a user is removed from a project.
    """
    # Notify the user about being removed
    create_notification(
        recipient=instance.user,
        notification_type='warning',
        title=f'Removed from project: {instance.project.name}',
        message=f'You have been removed from the project "{instance.project.name}".',
    )


@receiver(pre_save, sender=Project)
def project_pre_save(sender, instance, **kwargs):
    """
    Handle project changes before saving.
    """
    if instance.pk:  # Only for existing projects
        try:
            old_instance = Project.objects.get(pk=instance.pk)
            
            # Check for status changes
            if old_instance.status != instance.status:
                # Create a project update for status change
                from .models import ProjectUpdate
                
                # We'll create this in post_save to ensure the project is saved first
                instance._status_changed = True
                instance._old_status = old_instance.status
        except Project.DoesNotExist:
            pass


@receiver(post_save, sender=Project)
def project_status_changed(sender, instance, **kwargs):
    """
    Handle project status changes after saving.
    """
    if hasattr(instance, '_status_changed') and instance._status_changed:
        from .models import ProjectUpdate
        
        # Create project update for status change
        update_content = f'Project status changed from {instance._old_status} to {instance.status}.'
        
        ProjectUpdate.objects.create(
            project=instance,
            author=instance.project_manager or instance.tenant.tenant_users.filter(
                role='owner'
            ).first().user,
            update_type='status',
            title=f'Status Changed: {instance.get_status_display()}',
            content=update_content,
            progress_at_update=instance.progress_percentage,
            budget_spent_at_update=instance.budget_spent
        )
        
        # Notify team members about status change
        team_members = instance.team_members.all()
        for member in team_members:
            create_notification(
                recipient=member,
                notification_type='info',
                title=f'Project status updated: {instance.name}',
                message=update_content,
                action_url=instance.get_absolute_url(),
                action_label='View Project'
            )
        
        # Clean up temporary attributes
        delattr(instance, '_status_changed')
        delattr(instance, '_old_status')
