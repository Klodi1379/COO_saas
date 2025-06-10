"""
API Views for the REST API endpoints.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from .serializers import (
    UserSerializer, UserProfileSerializer, TenantSerializer,
    ProjectSerializer, ProjectCategorySerializer, TaskSerializer,
    SmartKPISerializer, KPICategorySerializer, KPIDataPointSerializer,
    KPIAlertSerializer, AutomationRuleSerializer, NotificationSerializer
)

from projects.models import Project, ProjectCategory, Task
from kpis.models import SmartKPI, KPICategory, KPIDataPoint, KPIAlert
from automation.models import AutomationRule
from core.models import Notification
from tenants.middleware import get_current_tenant
from core.utils import log_user_action


class TenantFilterMixin:
    """Mixin to filter queryset by current tenant."""
    
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = get_current_tenant()
        
        if tenant and hasattr(queryset.model, 'tenant'):
            return queryset.filter(tenant=tenant)
        
        return queryset


class ProjectCategoryViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    """API ViewSet for Project Categories."""
    queryset = ProjectCategory.objects.all()
    serializer_class = ProjectCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['is_active']
    
    def perform_create(self, serializer):
        tenant = get_current_tenant()
        serializer.save(tenant=tenant)


class ProjectViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    """API ViewSet for Projects."""
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['status', 'priority', 'category', 'project_manager']
    ordering_fields = ['name', 'created_at', 'target_end_date', 'progress_percentage']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('category', 'project_manager').prefetch_related('team_members')
    
    def perform_create(self, serializer):
        tenant = get_current_tenant()
        serializer.save(tenant=tenant)
    
    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        """Get tasks for a specific project."""
        project = self.get_object()
        tasks = project.tasks.all().select_related('assigned_to', 'created_by')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            tasks = tasks.filter(status=status_filter)
        
        assigned_to = request.query_params.get('assigned_to')
        if assigned_to:
            tasks = tasks.filter(assigned_to_id=assigned_to)
        
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get project analytics."""
        project = self.get_object()
        
        # Task statistics
        tasks = project.tasks.all()
        task_stats = {
            'total': tasks.count(),
            'completed': tasks.filter(status='completed').count(),
            'in_progress': tasks.filter(status='in_progress').count(),
            'todo': tasks.filter(status='todo').count(),
            'blocked': tasks.filter(status='blocked').count(),
        }
        
        # Progress over time (last 30 days)
        from django.db.models import Count
        from datetime import datetime
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        progress_data = []
        
        # This is a simplified version - in production you'd want more sophisticated tracking
        progress_data.append({
            'date': timezone.now().date().isoformat(),
            'progress': project.progress_percentage,
            'completed_tasks': task_stats['completed'],
            'total_tasks': task_stats['total']
        })
        
        return Response({
            'project_id': str(project.id),
            'task_statistics': task_stats,
            'progress_data': progress_data,
            'budget_utilization': project.budget_utilization,
            'is_overdue': project.is_overdue,
            'days_remaining': project.days_remaining,
        })


class TaskViewSet(viewsets.ModelViewSet):
    """API ViewSet for Tasks."""
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    filterset_fields = ['status', 'priority', 'assigned_to', 'project']
    ordering_fields = ['title', 'created_at', 'due_date', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        tenant = get_current_tenant()
        if tenant:
            return Task.objects.filter(project__tenant=tenant).select_related(
                'project', 'assigned_to', 'created_by'
            )
        return Task.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['patch'])
    def change_status(self, request, pk=None):
        """Change task status."""
        task = self.get_object()
        new_status = request.data.get('status')
        
        if new_status in dict(Task.STATUS_CHOICES):
            old_status = task.status
            task.status = new_status
            task.save()
            
            log_user_action(
                request, 'update', 'Task', str(task.id),
                f'Changed status from {old_status} to {new_status}'
            )
            
            return Response({'status': 'success', 'new_status': new_status})
        
        return Response(
            {'status': 'error', 'message': 'Invalid status'},
            status=status.HTTP_400_BAD_REQUEST
        )


class KPICategoryViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    """API ViewSet for KPI Categories."""
    queryset = KPICategory.objects.all()
    serializer_class = KPICategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['category_type', 'is_active']
    ordering = ['display_order', 'name']
    
    def perform_create(self, serializer):
        tenant = get_current_tenant()
        serializer.save(tenant=tenant)


class SmartKPIViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    """API ViewSet for Smart KPIs."""
    queryset = SmartKPI.objects.all()
    serializer_class = SmartKPISerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['category', 'data_source_type', 'is_active', 'is_featured', 'owner']
    ordering_fields = ['name', 'created_at']
    ordering = ['category', 'name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('category', 'owner').prefetch_related('stakeholders')
    
    def perform_create(self, serializer):
        tenant = get_current_tenant()
        if not serializer.validated_data.get('owner'):
            serializer.save(tenant=tenant, owner=self.request.user)
        else:
            serializer.save(tenant=tenant)
    
    @action(detail=True, methods=['get'])
    def data_points(self, request, pk=None):
        """Get data points for a KPI."""
        kpi = self.get_object()
        
        # Get query parameters
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 100))
        
        # Get data points
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        data_points = kpi.datapoints.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('-date')[:limit]
        
        serializer = KPIDataPointSerializer(data_points, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_data_point(self, request, pk=None):
        """Add a new data point to the KPI."""
        kpi = self.get_object()
        
        serializer = KPIDataPointSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                kpi=kpi,
                entered_by=request.user,
                source='manual'
            )
            
            log_user_action(
                request, 'create', 'KPIDataPoint',
                f'{kpi.id}:{serializer.instance.date}',
                f'Added data point for {kpi.name}'
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def trend(self, request, pk=None):
        """Get trend analysis for a KPI."""
        kpi = self.get_object()
        days = int(request.query_params.get('days', 30))
        
        trend_data = kpi.get_trend_data(days=days)
        
        return Response({
            'kpi_id': str(kpi.id),
            'kpi_name': kpi.name,
            'unit': kpi.unit,
            'trend_data': trend_data,
            'current_value': kpi.get_latest_value(),
            'target_value': kpi.target_value,
            'performance_status': kpi.calculate_performance_status(),
        })


class KPIAlertViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for KPI Alerts (read-only)."""
    queryset = KPIAlert.objects.all()
    serializer_class = KPIAlertSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['alert_type', 'severity', 'is_acknowledged', 'is_resolved']
    ordering = ['-created_at']
    
    def get_queryset(self):
        tenant = get_current_tenant()
        if tenant:
            return KPIAlert.objects.filter(kpi__tenant=tenant).select_related('kpi', 'acknowledged_by')
        return KPIAlert.objects.none()
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge an alert."""
        alert = self.get_object()
        alert.acknowledge(request.user)
        
        log_user_action(
            request, 'update', 'KPIAlert', str(alert.id),
            f'Acknowledged alert: {alert.title}'
        )
        
        return Response({'status': 'acknowledged'})


class AutomationRuleViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    """API ViewSet for Automation Rules."""
    queryset = AutomationRule.objects.all()
    serializer_class = AutomationRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['status', 'trigger_type', 'is_enabled']
    ordering_fields = ['name', 'created_at', 'last_triggered']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('created_by').prefetch_related('team_access', 'actions')
    
    def perform_create(self, serializer):
        tenant = get_current_tenant()
        serializer.save(tenant=tenant, created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Manually execute an automation rule."""
        rule = self.get_object()
        
        try:
            success = rule.execute()
            
            log_user_action(
                request, 'execute', 'AutomationRule', str(rule.id),
                f'Manually executed rule: {rule.name}'
            )
            
            return Response({
                'status': 'success' if success else 'partial',
                'execution_count': rule.execution_count,
                'last_triggered': rule.last_triggered
            })
            
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['patch'])
    def toggle_status(self, request, pk=None):
        """Toggle rule enabled/disabled status."""
        rule = self.get_object()
        rule.is_enabled = not rule.is_enabled
        rule.save(update_fields=['is_enabled'])
        
        log_user_action(
            request, 'update', 'AutomationRule', str(rule.id),
            f'{"Enabled" if rule.is_enabled else "Disabled"} rule'
        )
        
        return Response({'is_enabled': rule.is_enabled})


class NotificationViewSet(viewsets.ModelViewSet):
    """API ViewSet for Notifications."""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'is_read']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)
    
    @action(detail=True, methods=['patch'])
    def mark_read(self, request, pk=None):
        """Mark notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'is_read': True})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'marked_read': updated})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """Get dashboard summary data."""
    tenant = get_current_tenant()
    if not tenant:
        return Response({'error': 'No tenant found'}, status=404)
    
    # Projects summary
    projects = Project.objects.filter(tenant=tenant)
    project_stats = {
        'total': projects.count(),
        'active': projects.filter(status='active').count(),
        'completed': projects.filter(status='completed').count(),
        'overdue': sum(1 for p in projects if p.is_overdue),
    }
    
    # Tasks summary
    user_tasks = Task.objects.filter(
        project__tenant=tenant,
        assigned_to=request.user
    )
    task_stats = {
        'assigned_to_me': user_tasks.exclude(status='completed').count(),
        'overdue': sum(1 for t in user_tasks if t.is_overdue),
        'completed_today': user_tasks.filter(
            status='completed',
            completed_at__date=timezone.now().date()
        ).count(),
    }
    
    # KPIs summary
    kpis = SmartKPI.objects.filter(tenant=tenant, is_active=True)
    kpi_stats = {
        'total': kpis.count(),
        'featured': kpis.filter(is_featured=True).count(),
        'alerts': KPIAlert.objects.filter(
            kpi__tenant=tenant,
            is_resolved=False
        ).count(),
    }
    
    # Recent activity
    recent_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    return Response({
        'projects': project_stats,
        'tasks': task_stats,
        'kpis': kpi_stats,
        'recent_notifications': NotificationSerializer(recent_notifications, many=True).data,
        'timestamp': timezone.now()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def platform_analytics(request):
    """Get platform-wide analytics."""
    tenant = get_current_tenant()
    if not tenant:
        return Response({'error': 'No tenant found'}, status=404)
    
    # Time range
    days = int(request.GET.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Project analytics
    projects = Project.objects.filter(tenant=tenant)
    project_analytics = {
        'total_projects': projects.count(),
        'status_breakdown': list(
            projects.values('status').annotate(count=Count('id'))
        ),
        'recent_completions': projects.filter(
            status='completed',
            actual_end_date__gte=start_date
        ).count(),
    }
    
    # KPI analytics
    kpis = SmartKPI.objects.filter(tenant=tenant, is_active=True)
    kpi_analytics = {
        'total_kpis': kpis.count(),
        'category_breakdown': list(
            kpis.values('category__name').annotate(count=Count('id'))
        ),
        'performance_summary': {},
    }
    
    # Calculate performance summary
    performance_counts = {'excellent': 0, 'good': 0, 'warning': 0, 'critical': 0, 'unknown': 0}
    for kpi in kpis:
        status = kpi.calculate_performance_status()
        performance_counts[status] = performance_counts.get(status, 0) + 1
    
    kpi_analytics['performance_summary'] = performance_counts
    
    return Response({
        'date_range': {
            'start_date': start_date,
            'end_date': end_date,
            'days': days
        },
        'projects': project_analytics,
        'kpis': kpi_analytics,
        'generated_at': timezone.now()
    })
