"""
Utility functions for the core app.
"""
from django.contrib.auth.models import User
from django.utils import timezone
from .models import AuditLog


def log_user_action(request, action, content_type, object_id, change_message=''):
    """
    Log user actions for audit trail.
    
    Args:
        request: HttpRequest object
        action: Action performed (create, update, delete, etc.)
        content_type: Model name
        object_id: Object identifier
        change_message: Description of the change
    """
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action=action,
            content_type=content_type,
            object_id=str(object_id),
            object_repr=change_message or f'{content_type} {object_id}',
            change_message=change_message,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:200]
        )


def get_client_ip(request):
    """
    Get the client IP address from the request.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def create_notification(recipient, title, message, notification_type='info', 
                       action_url='', action_label='', metadata=None):
    """
    Create a notification for a user.
    
    Args:
        recipient: User object
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        action_url: URL for action button
        action_label: Label for action button
        metadata: Additional metadata as dict
    """
    from .models import Notification
    
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
        action_label=action_label,
        metadata=metadata or {}
    )


def send_notification_to_users(users, title, message, notification_type='info',
                              action_url='', action_label='', metadata=None):
    """
    Send notifications to multiple users.
    """
    notifications = []
    for user in users:
        notification = create_notification(
            recipient=user,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            action_label=action_label,
            metadata=metadata
        )
        notifications.append(notification)
    
    return notifications


def get_dashboard_context(user, tenant):
    """
    Get common dashboard context data.
    """
    context = {}
    
    if user and user.is_authenticated:
        # Get unread notifications count
        context['unread_notifications_count'] = user.notifications.filter(
            is_read=False
        ).count()
        
        # Get user's role and permissions
        profile = getattr(user, 'profile', None)
        if profile:
            context['user_role'] = profile.role
            context['user_permissions'] = {
                'can_manage_tenant': profile.can_manage_tenant,
                'is_consultant': profile.is_consultant,
                'is_client_admin': profile.is_client_admin,
            }
    
    if tenant:
        context['tenant'] = tenant
        context['tenant_settings'] = {
            'subscription_tier': tenant.subscription_tier,
            'is_active': tenant.is_active,
        }
    
    return context


def calculate_progress_percentage(completed, total):
    """
    Calculate progress percentage with proper handling of edge cases.
    """
    if total == 0:
        return 0
    return int((completed / total) * 100)


def format_currency(amount, currency_symbol='$'):
    """
    Format currency amount with proper formatting.
    """
    if amount is None:
        return f'{currency_symbol}0.00'
    
    return f'{currency_symbol}{amount:,.2f}'


def format_number(number, decimal_places=0):
    """
    Format numbers with proper thousand separators.
    """
    if number is None:
        return '0'
    
    if decimal_places > 0:
        return f'{number:,.{decimal_places}f}'
    else:
        return f'{int(number):,}'


def get_color_for_status(status):
    """
    Get Bootstrap color class for various status values.
    """
    color_map = {
        # Project statuses
        'planning': 'secondary',
        'active': 'primary',
        'on_hold': 'warning',
        'completed': 'success',
        'cancelled': 'danger',
        
        # Task statuses
        'todo': 'secondary',
        'in_progress': 'primary',
        'review': 'warning',
        'blocked': 'danger',
        
        # KPI performance
        'excellent': 'success',
        'good': 'primary',
        'warning': 'warning',
        'critical': 'danger',
        'unknown': 'secondary',
        
        # Priority levels
        'low': 'success',
        'medium': 'warning',
        'high': 'danger',
        'urgent': 'danger',
        'critical': 'danger',
    }
    
    return color_map.get(status.lower(), 'secondary')


def get_icon_for_type(item_type):
    """
    Get Font Awesome icon for various item types.
    """
    icon_map = {
        'project': 'project-diagram',
        'task': 'tasks',
        'kpi': 'chart-bar',
        'notification': 'bell',
        'user': 'user',
        'team': 'users',
        'dashboard': 'tachometer-alt',
        'report': 'file-alt',
        'calendar': 'calendar',
        'settings': 'cog',
        'automation': 'robot',
        'alert': 'exclamation-triangle',
        'success': 'check-circle',
        'info': 'info-circle',
        'warning': 'exclamation-triangle',
        'error': 'exclamation-circle',
    }
    
    return icon_map.get(item_type.lower(), 'circle')


def truncate_text(text, length=100, suffix='...'):
    """
    Truncate text to specified length with suffix.
    """
    if not text:
        return ''
    
    if len(text) <= length:
        return text
    
    return text[:length].rsplit(' ', 1)[0] + suffix


def time_ago(datetime_obj):
    """
    Get human-readable time ago string.
    """
    if not datetime_obj:
        return 'Never'
    
    now = timezone.now()
    diff = now - datetime_obj
    
    if diff.days > 0:
        return f'{diff.days} days ago'
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f'{hours} hours ago'
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f'{minutes} minutes ago'
    else:
        return 'Just now'


class PermissionChecker:
    """
    Helper class for checking user permissions.
    """
    
    def __init__(self, user, tenant=None):
        self.user = user
        self.tenant = tenant
        self.profile = getattr(user, 'profile', None)
    
    def can_view_project(self, project):
        """Check if user can view a specific project."""
        if not self.user.is_authenticated:
            return False
        
        # System admin can view all
        if self.user.is_superuser:
            return True
        
        # Must be in same tenant
        if self.tenant and project.tenant != self.tenant:
            return False
        
        # Project manager or team member can view
        if project.project_manager == self.user:
            return True
        
        # Check if user is team member
        return project.team_members.filter(id=self.user.id).exists()
    
    def can_edit_project(self, project):
        """Check if user can edit a specific project."""
        if not self.can_view_project(project):
            return False
        
        # System admin can edit all
        if self.user.is_superuser:
            return True
        
        # Client admin can edit projects in their tenant
        if self.profile and self.profile.is_client_admin:
            return True
        
        # Project manager can edit
        if project.project_manager == self.user:
            return True
        
        # Check if user has edit permissions as team member
        membership = project.projectmembership_set.filter(user=self.user).first()
        return membership and membership.can_edit_project
    
    def can_manage_tenant(self):
        """Check if user can manage tenant settings."""
        return (self.user.is_superuser or 
                (self.profile and self.profile.can_manage_tenant))
    
    def can_create_project(self):
        """Check if user can create projects."""
        if not self.user.is_authenticated:
            return False
        
        return (self.user.is_superuser or 
                (self.profile and self.profile.role in ['client_admin', 'consultant']))
    
    def can_view_kpi(self, kpi):
        """Check if user can view a specific KPI."""
        if not self.user.is_authenticated:
            return False
        
        if self.user.is_superuser:
            return True
        
        # Must be in same tenant
        if self.tenant and kpi.tenant != self.tenant:
            return False
        
        # KPI owner can view
        if kpi.owner == self.user:
            return True
        
        # Stakeholders can view
        return kpi.stakeholders.filter(id=self.user.id).exists()