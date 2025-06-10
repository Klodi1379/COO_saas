"""
Core views for common functionality.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from .models import Notification, AuditLog
from .utils import log_user_action


class DashboardMixin(LoginRequiredMixin):
    """
    Mixin for dashboard views with common functionality.
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Add common dashboard data
        context.update({
            'recent_notifications': user.notifications.filter(is_read=False)[:5],
            'user_profile': getattr(user, 'profile', None),
        })
        
        return context


@login_required
def notifications_list(request):
    """
    Display user notifications.
    """
    notifications = request.user.notifications.all()
    
    # Mark notifications as read if requested
    if request.method == 'POST' and 'mark_read' in request.POST:
        notification_ids = request.POST.getlist('notification_ids')
        Notification.objects.filter(
            id__in=notification_ids,
            recipient=request.user
        ).update(is_read=True)
        messages.success(request, 'Notifications marked as read.')
        return redirect('core:notifications')
    
    context = {
        'notifications': notifications,
        'unread_count': notifications.filter(is_read=False).count(),
    }
    
    return render(request, 'core/notifications.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """
    Mark a single notification as read (AJAX endpoint).
    """
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user
            )
            notification.mark_as_read()
            
            return JsonResponse({
                'success': True,
                'unread_count': request.user.notifications.filter(is_read=False).count()
            })
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notification not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def user_activity_log(request):
    """
    Display user's activity log.
    """
    logs = AuditLog.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by action if specified
    action_filter = request.GET.get('action')
    if action_filter:
        logs = logs.filter(action=action_filter)
    
    # Filter by date range if specified
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)
    
    context = {
        'logs': logs[:100],  # Limit to 100 most recent
        'action_choices': AuditLog.ACTION_CHOICES,
        'current_filters': {
            'action': action_filter,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'core/activity_log.html', context)


class ProfileView(LoginRequiredMixin, TemplateView):
    """
    User profile view and settings.
    """
    template_name = 'core/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_profile'] = getattr(self.request.user, 'profile', None)
        return context
    
    def post(self, request, *args, **kwargs):
        """
        Handle profile updates.
        """
        user = request.user
        profile = getattr(user, 'profile', None)
        
        if not profile:
            messages.error(request, 'Profile not found.')
            return redirect('core:profile')
        
        # Update basic user information
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', user.email)
        user.save()
        
        # Update profile information
        profile.phone = request.POST.get('phone', '')
        profile.timezone = request.POST.get('timezone', profile.timezone)
        profile.email_notifications = request.POST.get('email_notifications') == 'on'
        
        # Handle avatar upload
        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        
        profile.save()
        
        log_user_action(request, 'update', 'UserProfile', str(profile.id), 'Profile updated')
        messages.success(request, 'Profile updated successfully.')
        
        return redirect('core:profile')


@login_required
def search_global(request):
    """
    Global search across the platform.
    """
    query = request.GET.get('q', '').strip()
    results = {
        'projects': [],
        'tasks': [],
        'kpis': [],
        'notifications': [],
    }
    
    if query and len(query) >= 3:
        # Search notifications
        notifications = request.user.notifications.filter(
            Q(title__icontains=query) | Q(message__icontains=query)
        )[:5]
        results['notifications'] = [{
            'id': n.id,
            'title': n.title,
            'type': n.notification_type,
            'created_at': n.created_at,
            'url': n.action_url or '#'
        } for n in notifications]
        
        # TODO: Add search for projects, tasks, KPIs when those apps are implemented
    
    if request.headers.get('accept') == 'application/json':
        return JsonResponse(results)
    
    context = {
        'query': query,
        'results': results,
    }
    
    return render(request, 'core/search_results.html', context)



@login_required
def notifications_api(request):
    """
    API endpoint for loading notifications (for dropdown).
    """
    notifications = request.user.notifications.order_by('-created_at')[:10]
    
    data = {
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.notification_type,
                'read': n.is_read,
                'created_at': n.created_at.strftime('%b %d, %Y at %I:%M %p'),
                'icon': {
                    'info': 'info-circle',
                    'success': 'check-circle',
                    'warning': 'exclamation-triangle',
                    'error': 'exclamation-circle',
                    'task_assigned': 'tasks',
                    'task_completed': 'check',
                    'kpi_alert': 'chart-bar',
                    'deadline_approaching': 'clock',
                    'system': 'cog'
                }.get(n.notification_type, 'bell')
            }
            for n in notifications
        ],
        'unread_count': request.user.notifications.filter(is_read=False).count()
    }
    
    return JsonResponse(data)