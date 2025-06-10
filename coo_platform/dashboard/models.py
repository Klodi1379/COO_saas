"""
Dashboard models for the main interface.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import TimeStampedModel, UUIDModel
from tenants.models import TenantAwareModel
from datetime import datetime, timedelta


class DashboardWidget(UUIDModel, TenantAwareModel, TimeStampedModel):
    """
    Individual widgets that can be placed on dashboards.
    """
    WIDGET_TYPES = [
        ('kpi_summary', 'KPI Summary'),
        ('kpi_chart', 'KPI Chart'),
        ('project_overview', 'Project Overview'),
        ('task_list', 'Task List'),
        ('recent_activity', 'Recent Activity'),
        ('alerts_summary', 'Alerts Summary'),
        ('team_performance', 'Team Performance'),
        ('calendar', 'Calendar'),
        ('notes', 'Notes'),
        ('custom_metric', 'Custom Metric'),
        ('external_embed', 'External Embed'),
    ]
    
    SIZE_CHOICES = [
        ('small', 'Small (1x1)'),
        ('medium', 'Medium (2x1)'),
        ('large', 'Large (2x2)'),
        ('wide', 'Wide (3x1)'),
        ('tall', 'Tall (1x3)'),
        ('extra_large', 'Extra Large (3x2)'),
    ]
    
    # Basic Information
    title = models.CharField(max_length=200)
    widget_type = models.CharField(max_length=30, choices=WIDGET_TYPES)
    description = models.TextField(blank=True)
    
    # Configuration
    config = models.JSONField(
        default=dict,
        help_text="Widget-specific configuration"
    )
    size = models.CharField(max_length=20, choices=SIZE_CHOICES, default='medium')
    
    # Data source settings
    refresh_interval = models.PositiveIntegerField(
        default=300,
        help_text="Auto-refresh interval in seconds"
    )
    cache_duration = models.PositiveIntegerField(
        default=60,
        help_text="Cache duration in seconds"
    )
    
    # Ownership and sharing
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_widgets')
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(
        User,
        blank=True,
        related_name='shared_widgets'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['title']
        indexes = [
            models.Index(fields=['tenant', 'widget_type']),
            models.Index(fields=['created_by', 'is_active']),
        ]
    
    def __str__(self):
        return self.title
    
    def get_data(self, user=None):
        """
        Get widget data based on its type and configuration.
        """
        if not self.is_active:
            return {'error': 'Widget is not active'}
        
        try:
            if self.widget_type == 'kpi_summary':
                return self._get_kpi_summary_data()
            elif self.widget_type == 'kpi_chart':
                return self._get_kpi_chart_data()
            elif self.widget_type == 'project_overview':
                return self._get_project_overview_data()
            elif self.widget_type == 'task_list':
                return self._get_task_list_data(user)
            elif self.widget_type == 'recent_activity':
                return self._get_recent_activity_data()
            elif self.widget_type == 'alerts_summary':
                return self._get_alerts_summary_data()
            else:
                return {'message': 'Widget type not implemented yet'}
        except Exception as e:
            return {'error': str(e)}
    
    def _get_kpi_summary_data(self):
        """Get KPI summary data."""
        from kpis.models import SmartKPI
        
        kpi_ids = self.config.get('kpi_ids', [])
        limit = self.config.get('limit', 4)
        
        if kpi_ids:
            kpis = SmartKPI.objects.filter(
                id__in=kpi_ids,
                tenant=self.tenant,
                is_active=True
            )
        else:
            # If no specific KPIs configured, get featured KPIs
            kpis = SmartKPI.objects.filter(
                tenant=self.tenant,
                is_active=True,
                is_featured=True
            )[:limit]
        
        if not kpis.exists():
            return {'kpis': [], 'message': 'No KPIs configured'}
        
        data = []
        for kpi in kpis:
            current_value = kpi.get_latest_value()
            data.append({
                'id': str(kpi.id),
                'name': kpi.name,
                'current_value': float(current_value) if current_value else None,
                'target_value': float(kpi.target_value) if kpi.target_value else None,
                'unit': kpi.unit,
                'performance_status': kpi.calculate_performance_status(),
                'category_color': kpi.category.color if kpi.category else '#007bff'
            })
        
        return {'kpis': data}
    
    def _get_kpi_chart_data(self):
        """Get KPI chart data."""
        from kpis.models import SmartKPI
        
        kpi_id = self.config.get('kpi_id')
        days = self.config.get('days', 30)
        
        if not kpi_id:
            return {'error': 'No KPI configured'}
        
        try:
            kpi = SmartKPI.objects.get(id=kpi_id, tenant=self.tenant)
            trend_data = kpi.get_trend_data(days=days)
            
            return {
                'kpi_name': kpi.name,
                'unit': kpi.unit,
                'trend_data': trend_data,
                'chart_type': self.config.get('chart_type', 'line')
            }
        except SmartKPI.DoesNotExist:
            return {'error': 'KPI not found'}
    
    def _get_project_overview_data(self):
        """Get project overview data."""
        from projects.models import Project
        from django.db.models import Count, Q
        
        projects = Project.objects.filter(tenant=self.tenant)
        
        # Get project status breakdown
        status_breakdown = projects.values('status').annotate(count=Count('id'))
        
        # Get overdue projects
        overdue_count = sum(1 for p in projects if p.is_overdue)
        
        # Get recent projects
        recent_projects = projects.order_by('-created_at')[:5]
        
        return {
            'total_projects': projects.count(),
            'status_breakdown': list(status_breakdown),
            'overdue_count': overdue_count,
            'recent_projects': [
                {
                    'id': str(p.id),
                    'name': p.name,
                    'status': p.status,
                    'progress': p.progress_percentage,
                }
                for p in recent_projects
            ]
        }
    
    def _get_task_list_data(self, user):
        """Get task list data."""
        from projects.models import Task
        
        filter_type = self.config.get('filter_type', 'assigned_to_me')
        limit = self.config.get('limit', 10)
        
        if filter_type == 'assigned_to_me' and user:
            tasks_queryset = Task.objects.filter(
                assigned_to=user,
                project__tenant=self.tenant
            ).exclude(status='completed')
        elif filter_type == 'recent':
            tasks_queryset = Task.objects.filter(
                project__tenant=self.tenant
            ).order_by('-created_at')
        elif filter_type == 'overdue':
            tasks_queryset = Task.objects.filter(
                project__tenant=self.tenant,
                due_date__lt=timezone.now()
            ).exclude(status='completed')
        else:
            tasks_queryset = Task.objects.filter(
                project__tenant=self.tenant
            )
        
        total_count = tasks_queryset.count()
        tasks = tasks_queryset.select_related('project', 'assigned_to')[:limit]
        
        return {
            'tasks': [
                {
                    'id': str(t.id),
                    'title': t.title,
                    'project_name': t.project.name,
                    'status': t.status,
                    'priority': t.priority,
                    'due_date': t.due_date.isoformat() if t.due_date else None,
                    'assigned_to': t.assigned_to.get_full_name() if t.assigned_to else None,
                    'is_overdue': t.is_overdue,
                }
                for t in tasks
            ],
            'total_count': total_count
        }
    
    def _get_recent_activity_data(self):
        """Get recent activity data."""
        from core.models import AuditLog
        from tenants.models import TenantUser
        
        limit = self.config.get('limit', 10)
        
        # Get users in this tenant
        tenant_users = TenantUser.objects.filter(tenant=self.tenant).values_list('user_id', flat=True)
        
        logs = AuditLog.objects.filter(
            user_id__in=tenant_users
        ).select_related('user').order_by('-created_at')[:limit]
        
        return {
            'activities': [
                {
                    'id': str(log.id),
                    'title': f"{log.get_action_display()} {log.content_type}",
                    'description': log.object_repr or log.change_message,
                    'type': log.action,
                    'user': log.user.get_full_name() if log.user else 'System',
                    'created_at': log.created_at.isoformat(),
                }
                for log in logs
            ]
        }
    
    def _get_alerts_summary_data(self):
        """Get alerts summary data."""
        from kpis.models import KPIAlert
        from django.db.models import Count
        
        limit = self.config.get('limit', 10)
        
        alerts_queryset = KPIAlert.objects.filter(
            kpi__tenant=self.tenant,
            is_resolved=False
        )
        
        total_count = alerts_queryset.count()
        alerts = alerts_queryset.select_related('kpi').order_by('-created_at')[:limit]
        
        return {
            'alerts': [
                {
                    'id': str(a.id),
                    'title': a.title,
                    'message': a.message,
                    'severity': a.severity,
                    'kpi_name': a.kpi.name,
                    'created_at': a.created_at.isoformat(),
                    'is_acknowledged': a.is_acknowledged,
                }
                for a in alerts
            ],
            'total_count': total_count,
            'severity_breakdown': list(alerts_queryset.values('severity').annotate(count=Count('id')))
        }


class UserDashboard(UUIDModel, TenantAwareModel, TimeStampedModel):
    """
    User's personalized dashboard configuration.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboards')
    name = models.CharField(max_length=200, default='My Dashboard')
    is_default = models.BooleanField(default=False)
    
    # Layout configuration
    layout_config = models.JSONField(
        default=dict,
        help_text="Dashboard layout and grid configuration"
    )
    
    # Settings
    auto_refresh = models.BooleanField(default=True)
    refresh_interval = models.PositiveIntegerField(
        default=300,
        help_text="Dashboard refresh interval in seconds"
    )
    
    class Meta:
        unique_together = ['user', 'tenant', 'name']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"
    
    def get_widgets(self):
        """Get all widgets for this dashboard."""
        return self.widget_placements.select_related('widget').order_by('position_y', 'position_x')


class DashboardWidgetPlacement(UUIDModel, TimeStampedModel):
    """
    Placement of widgets on a dashboard with position and size.
    """
    dashboard = models.ForeignKey(
        UserDashboard, 
        on_delete=models.CASCADE, 
        related_name='widget_placements'
    )
    widget = models.ForeignKey(
        DashboardWidget, 
        on_delete=models.CASCADE,
        related_name='placements'
    )
    
    # Grid position
    position_x = models.PositiveIntegerField(default=0)
    position_y = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=2)
    height = models.PositiveIntegerField(default=2)
    
    # Widget-specific overrides
    title_override = models.CharField(max_length=200, blank=True)
    config_override = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['dashboard', 'widget']
        ordering = ['position_y', 'position_x']
    
    def __str__(self):
        return f"{self.dashboard.name} - {self.widget.title}"


class DashboardTheme(UUIDModel, TenantAwareModel, TimeStampedModel):
    """
    Dashboard themes for customization.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Color scheme
    primary_color = models.CharField(max_length=7, default='#007bff')
    secondary_color = models.CharField(max_length=7, default='#6c757d')
    background_color = models.CharField(max_length=7, default='#ffffff')
    text_color = models.CharField(max_length=7, default='#333333')
    
    # Style configuration
    theme_config = models.JSONField(
        default=dict,
        help_text="Additional theme configuration"
    )
    
    # Availability
    is_public = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
