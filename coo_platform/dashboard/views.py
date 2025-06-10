"""
Views for the main dashboard interface.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    DashboardWidget, UserDashboard, DashboardWidgetPlacement, DashboardTheme
)
from core.views import DashboardMixin
from core.utils import log_user_action
from tenants.middleware import get_current_tenant


class MainDashboardView(DashboardMixin, LoginRequiredMixin, TemplateView):
    """
    Main dashboard view - the primary interface users see.
    """
    template_name = 'dashboard/main.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant()
        user = self.request.user
        
        if not tenant:
            context['error'] = 'No tenant found'
            return context
        
        # Get or create user's default dashboard
        dashboard, created = UserDashboard.objects.get_or_create(
            user=user,
            tenant=tenant,
            is_default=True,
            defaults={
                'name': 'My Dashboard',
                'layout_config': {
                    'columns': 12,
                    'row_height': 150,
                    'margin': [10, 10]
                }
            }
        )
        
        if created:
            # Create default widgets for new dashboard
            self._create_default_widgets(dashboard)
        
        # Get dashboard widgets
        widget_placements = dashboard.get_widgets()
        
        # Get quick stats for the overview
        quick_stats = self._get_quick_stats(tenant, user)
        
        context.update({
            'dashboard': dashboard,
            'widget_placements': widget_placements,
            'quick_stats': quick_stats,
            'available_widgets': DashboardWidget.objects.filter(
                tenant=tenant,
                is_active=True
            ),
        })
        
        return context
    
    def _create_default_widgets(self, dashboard):
        """Create default widgets for a new dashboard."""
        default_widgets = [
            {
                'title': 'KPI Overview',
                'widget_type': 'kpi_summary',
                'position': (0, 0),
                'size': (6, 3),
                'config': {'limit': 4}
            },
            {
                'title': 'My Tasks',
                'widget_type': 'task_list',
                'position': (6, 0),
                'size': (6, 3),
                'config': {'filter_type': 'assigned_to_me', 'limit': 8}
            },
            {
                'title': 'Project Overview',
                'widget_type': 'project_overview',
                'position': (0, 3),
                'size': (8, 3),
                'config': {}
            },
            {
                'title': 'Alerts',
                'widget_type': 'alerts_summary',
                'position': (8, 3),
                'size': (4, 3),
                'config': {'limit': 5}
            },
        ]
        
        for widget_data in default_widgets:
            # Create widget
            widget = DashboardWidget.objects.create(
                tenant=dashboard.tenant,
                title=widget_data['title'],
                widget_type=widget_data['widget_type'],
                config=widget_data['config'],
                created_by=dashboard.user,
                size='medium'
            )
            
            # Place widget on dashboard
            DashboardWidgetPlacement.objects.create(
                dashboard=dashboard,
                widget=widget,
                position_x=widget_data['position'][0],
                position_y=widget_data['position'][1],
                width=widget_data['size'][0],
                height=widget_data['size'][1]
            )
    
    def _get_quick_stats(self, tenant, user):
        """Get quick statistics for the dashboard overview."""
        from projects.models import Project, Task
        from kpis.models import SmartKPI, KPIAlert
        
        stats = {}
        
        try:
            # Project stats
            projects = Project.objects.filter(tenant=tenant)
            stats['total_projects'] = projects.count()
            stats['active_projects'] = projects.filter(status='active').count()
            stats['overdue_projects'] = sum(1 for p in projects if p.is_overdue)
            
            # Task stats
            user_tasks = Task.objects.filter(
                project__tenant=tenant,
                assigned_to=user
            )
            stats['my_tasks'] = user_tasks.exclude(status='completed').count()
            stats['overdue_tasks'] = sum(1 for t in user_tasks if t.is_overdue)
            
            # KPI stats
            kpis = SmartKPI.objects.filter(tenant=tenant, is_active=True)
            stats['total_kpis'] = kpis.count()
            stats['critical_alerts'] = KPIAlert.objects.filter(
                kpi__tenant=tenant,
                severity='critical',
                is_resolved=False
            ).count()
            
        except Exception as e:
            # If there's an error, return empty stats
            stats = {
                'total_projects': 0,
                'active_projects': 0,
                'overdue_projects': 0,
                'my_tasks': 0,
                'overdue_tasks': 0,
                'total_kpis': 0,
                'critical_alerts': 0,
            }
        
        return stats


@login_required
def widget_data_api(request, widget_id):
    """
    API endpoint to get widget data.
    """
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant found'}, status=404)
    
    try:
        widget = DashboardWidget.objects.get(
            id=widget_id,
            tenant=tenant
        )
    except DashboardWidget.DoesNotExist:
        return JsonResponse({'error': 'Widget not found'}, status=404)
    
    # Check permissions
    if not widget.is_public and widget.created_by != request.user:
        if request.user not in widget.shared_with.all():
            return JsonResponse({'error': 'Permission denied'}, status=403)
    
    data = widget.get_data(user=request.user)
    
    return JsonResponse({
        'widget_id': str(widget.id),
        'title': widget.title,
        'widget_type': widget.widget_type,
        'data': data,
        'last_updated': timezone.now().isoformat()
    })


@login_required
def update_dashboard_layout(request):
    """
    Update dashboard layout via AJAX.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant found'})
    
    try:
        dashboard_id = request.POST.get('dashboard_id')
        layout_data = request.POST.get('layout_data')
        
        if not dashboard_id or not layout_data:
            return JsonResponse({'success': False, 'error': 'Missing data'})
        
        dashboard = UserDashboard.objects.get(
            id=dashboard_id,
            user=request.user,
            tenant=tenant
        )
        
        import json
        layout = json.loads(layout_data)
        
        # Update widget positions
        for item in layout:
            widget_placement_id = item.get('id')
            x = item.get('x', 0)
            y = item.get('y', 0)
            w = item.get('w', 2)
            h = item.get('h', 2)
            
            try:
                placement = DashboardWidgetPlacement.objects.get(
                    id=widget_placement_id,
                    dashboard=dashboard
                )
                placement.position_x = x
                placement.position_y = y
                placement.width = w
                placement.height = h
                placement.save()
            except DashboardWidgetPlacement.DoesNotExist:
                continue
        
        log_user_action(
            request, 'update', 'UserDashboard',
            str(dashboard.id), 'Updated dashboard layout'
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def add_widget_to_dashboard(request):
    """
    Add a widget to user's dashboard.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant found'})
    
    try:
        widget_id = request.POST.get('widget_id')
        dashboard_id = request.POST.get('dashboard_id')
        
        widget = DashboardWidget.objects.get(id=widget_id, tenant=tenant)
        dashboard = UserDashboard.objects.get(
            id=dashboard_id,
            user=request.user,
            tenant=tenant
        )
        
        # Check if widget is already on dashboard
        if DashboardWidgetPlacement.objects.filter(
            dashboard=dashboard,
            widget=widget
        ).exists():
            return JsonResponse({'success': False, 'error': 'Widget already on dashboard'})
        
        # Find next available position
        existing_placements = DashboardWidgetPlacement.objects.filter(
            dashboard=dashboard
        ).values_list('position_x', 'position_y', 'width', 'height')
        
        # Simple positioning logic - place at bottom
        max_y = 0
        for placement in existing_placements:
            max_y = max(max_y, placement[1] + placement[3])
        
        # Create placement
        DashboardWidgetPlacement.objects.create(
            dashboard=dashboard,
            widget=widget,
            position_x=0,
            position_y=max_y,
            width=4,
            height=3
        )
        
        log_user_action(
            request, 'create', 'DashboardWidgetPlacement',
            f'{dashboard.id}:{widget.id}', f'Added widget {widget.title} to dashboard'
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def remove_widget_from_dashboard(request, placement_id):
    """
    Remove a widget from dashboard.
    """
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant found'})
    
    try:
        placement = DashboardWidgetPlacement.objects.get(
            id=placement_id,
            dashboard__user=request.user,
            dashboard__tenant=tenant
        )
        
        widget_title = placement.widget.title
        placement.delete()
        
        log_user_action(
            request, 'delete', 'DashboardWidgetPlacement',
            str(placement_id), f'Removed widget {widget_title} from dashboard'
        )
        
        return JsonResponse({'success': True})
        
    except DashboardWidgetPlacement.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Widget placement not found'})


class DashboardSettingsView(LoginRequiredMixin, TemplateView):
    """
    Dashboard settings and customization.
    """
    template_name = 'dashboard/settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant()
        
        if tenant:
            context.update({
                'user_dashboards': UserDashboard.objects.filter(
                    user=self.request.user,
                    tenant=tenant
                ),
                'available_themes': DashboardTheme.objects.filter(
                    Q(tenant=tenant) | Q(is_public=True)
                ),
                'available_widgets': DashboardWidget.objects.filter(
                    tenant=tenant,
                    is_active=True
                ),
            })
        
        return context


@login_required
def dashboard_export(request):
    """
    Export dashboard configuration.
    """
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant found'}, status=404)
    
    dashboard_id = request.GET.get('dashboard_id')
    if not dashboard_id:
        return JsonResponse({'error': 'Dashboard ID required'}, status=400)
    
    try:
        dashboard = UserDashboard.objects.get(
            id=dashboard_id,
            user=request.user,
            tenant=tenant
        )
        
        # Export dashboard configuration
        export_data = {
            'dashboard_name': dashboard.name,
            'layout_config': dashboard.layout_config,
            'widgets': []
        }
        
        for placement in dashboard.get_widgets():
            export_data['widgets'].append({
                'widget_title': placement.widget.title,
                'widget_type': placement.widget.widget_type,
                'widget_config': placement.widget.config,
                'position_x': placement.position_x,
                'position_y': placement.position_y,
                'width': placement.width,
                'height': placement.height,
                'title_override': placement.title_override,
                'config_override': placement.config_override,
            })
        
        return JsonResponse(export_data)
        
    except UserDashboard.DoesNotExist:
        return JsonResponse({'error': 'Dashboard not found'}, status=404)


@login_required
def real_time_updates(request):
    """
    Get real-time updates for dashboard widgets.
    """
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant found'}, status=404)
    
    # Get widgets that need updating
    widget_ids = request.GET.getlist('widget_ids')
    if not widget_ids:
        return JsonResponse({'updates': []})
    
    updates = []
    
    for widget_id in widget_ids:
        try:
            widget = DashboardWidget.objects.get(
                id=widget_id,
                tenant=tenant
            )
            
            # Check if user has access
            if widget.is_public or widget.created_by == request.user or \
               request.user in widget.shared_with.all():
                
                data = widget.get_data(user=request.user)
                updates.append({
                    'widget_id': widget_id,
                    'data': data,
                    'timestamp': timezone.now().isoformat()
                })
                
        except DashboardWidget.DoesNotExist:
            continue
    
    return JsonResponse({'updates': updates})
