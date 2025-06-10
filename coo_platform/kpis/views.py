"""
Views for KPI management and analytics.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Avg, Max, Min
from django.utils import timezone
from django.urls import reverse_lazy
from datetime import datetime, timedelta
from decimal import Decimal
from .models import (
    SmartKPI, KPICategory, KPIDataPoint, KPIAlert, 
    KPIDashboard, DashboardKPI
)
from core.views import DashboardMixin
from core.utils import log_user_action, create_notification
from tenants.middleware import get_current_tenant
import json


class KPIListView(DashboardMixin, LoginRequiredMixin, ListView):
    """
    List all KPIs for the current tenant.
    """
    model = SmartKPI
    template_name = 'kpis/smartkpi_list.html'
    context_object_name = 'kpis'
    paginate_by = 20
    
    def get_queryset(self):
        tenant = get_current_tenant()
        if not tenant:
            return SmartKPI.objects.none()
        
        queryset = SmartKPI.objects.filter(
            tenant=tenant, 
            is_active=True
        ).select_related('category', 'owner').prefetch_related('stakeholders')
        
        # Filter by category if specified
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Filter by data source type
        source_type = self.request.GET.get('source_type')
        if source_type:
            queryset = queryset.filter(data_source_type=source_type)
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )
        
        # Sort by parameter
        sort_by = self.request.GET.get('sort', 'category')
        if sort_by in ['name', '-name', 'category', '-category', 'created_at', '-created_at']:
            queryset = queryset.order_by(sort_by)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant()
        
        if tenant:
            categories = KPICategory.objects.filter(tenant=tenant, is_active=True)
            
            # Build filter configuration for search_filters component
            filter_config = [
                {
                    'name': 'category',
                    'label': 'Category',
                    'type': 'select',
                    'width': '3',
                    'options': [
                        {'value': cat.id, 'label': cat.name} 
                        for cat in categories
                    ]
                },
                {
                    'name': 'source_type',
                    'label': 'Data Source',
                    'type': 'select',
                    'width': '3',
                    'options': [
                        {'value': value, 'label': label} 
                        for value, label in SmartKPI.DATA_SOURCE_TYPES
                    ]
                },
                {
                    'name': 'sort',
                    'label': 'Sort By',
                    'type': 'select',
                    'width': '2',
                    'options': [
                        {'value': 'category', 'label': 'Category'},
                        {'value': '-category', 'label': 'Category (desc)'},
                        {'value': 'name', 'label': 'Name'},
                        {'value': '-name', 'label': 'Name (desc)'},
                        {'value': 'created_at', 'label': 'Created'},
                        {'value': '-created_at', 'label': 'Created (desc)'},
                    ]
                }
            ]
            
            context.update({
                'categories': categories,
                'source_types': SmartKPI.DATA_SOURCE_TYPES,
                'filter_config': filter_config,
                'current_filters': {
                    'category': self.request.GET.get('category', ''),
                    'source_type': self.request.GET.get('source_type', ''),
                    'search': self.request.GET.get('search', ''),
                    'sort': self.request.GET.get('sort', 'category'),
                },
                # Stats for overview cards
                'total_kpis': SmartKPI.objects.filter(tenant=tenant).count(),
                'active_kpis': SmartKPI.objects.filter(tenant=tenant, is_active=True).count(),
                'critical_alerts': KPIAlert.objects.filter(
                    kpi__tenant=tenant, 
                    severity='critical', 
                    is_resolved=False
                ).count(),
                'total_categories': categories.count(),
            })
        
        return context


class KPIDetailView(DashboardMixin, LoginRequiredMixin, DetailView):
    """
    Detailed view of a single KPI with analytics.
    """
    model = SmartKPI
    template_name = 'kpis/smartkpi_detail.html'
    context_object_name = 'kpi'
    
    def get_queryset(self):
        tenant = get_current_tenant()
        if not tenant:
            return SmartKPI.objects.none()
        return SmartKPI.objects.filter(tenant=tenant)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kpi = self.object
        
        # Get recent data points
        recent_datapoints = kpi.datapoints.order_by('-date')[:30]
        
        # Get trend data for charts
        trend_data = kpi.get_trend_data(days=90)
        
        # Get recent alerts
        recent_alerts = kpi.alerts.filter(is_resolved=False).order_by('-created_at')[:10]
        
        # Calculate basic statistics
        if recent_datapoints:
            values = [dp.value for dp in recent_datapoints]
            stats = {
                'current': values[0] if values else None,
                'previous': values[1] if len(values) > 1 else None,
                'average': sum(values) / len(values) if values else None,
                'min': min(values) if values else None,
                'max': max(values) if values else None,
            }
            
            # Calculate change from previous period
            if stats['current'] and stats['previous']:
                change = ((stats['current'] - stats['previous']) / stats['previous']) * 100
                stats['change_percent'] = round(float(change), 2)
            else:
                stats['change_percent'] = None
        else:
            stats = {
                'current': None,
                'previous': None,
                'average': None,
                'min': None,
                'max': None,
                'change_percent': None,
            }
        
        context.update({
            'recent_datapoints': recent_datapoints,
            'trend_data': json.dumps(trend_data),
            'recent_alerts': recent_alerts,
            'stats': stats,
            'performance_status': kpi.calculate_performance_status(),
        })
        
        return context


class KPICreateView(LoginRequiredMixin, CreateView):
    """
    Create a new KPI.
    """
    model = SmartKPI
    template_name = 'kpis/smartkpi_form.html'
    fields = [
        'name', 'description', 'category', 'data_source_type',
        'calculation_method', 'unit', 'decimal_places',
        'target_value', 'warning_threshold', 'critical_threshold',
        'trend_direction', 'auto_update_frequency', 'owner',
        'chart_type', 'is_featured'
    ]
    
    def form_valid(self, form):
        tenant = get_current_tenant()
        if not tenant:
            messages.error(self.request, 'No tenant found.')
            return redirect('kpis:list')
        
        form.instance.tenant = tenant
        if not form.instance.owner:
            form.instance.owner = self.request.user
        
        response = super().form_valid(form)
        
        # Schedule next update if automated
        if self.object.auto_update_frequency:
            self.object.schedule_next_update()
        
        log_user_action(
            self.request, 'create', 'SmartKPI', 
            str(self.object.id), f'Created KPI: {self.object.name}'
        )
        
        messages.success(self.request, f'KPI "{self.object.name}" created successfully.')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant()
        
        if tenant:
            context['categories'] = KPICategory.objects.filter(
                tenant=tenant, is_active=True
            )
        
        return context


@login_required
def add_kpi_datapoint(request, kpi_id):
    """
    Add a new data point to a KPI.
    """
    tenant = get_current_tenant()
    if not tenant:
        messages.error(request, 'No tenant found.')
        return redirect('kpis:list')
    
    kpi = get_object_or_404(SmartKPI, id=kpi_id, tenant=tenant)
    
    if request.method == 'POST':
        date_str = request.POST.get('date')
        value_str = request.POST.get('value')
        notes = request.POST.get('notes', '')
        
        if not date_str or not value_str:
            messages.error(request, 'Date and value are required.')
            return redirect('kpis:detail', pk=kpi_id)
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            value = Decimal(value_str)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date or value format.')
            return redirect('kpis:detail', pk=kpi_id)
        
        # Check if data point already exists for this date
        existing = KPIDataPoint.objects.filter(kpi=kpi, date=date).first()
        if existing:
            # Update existing data point
            existing.value = value
            existing.notes = notes
            existing.entered_by = request.user
            existing.save()
            action = 'updated'
        else:
            # Create new data point
            KPIDataPoint.objects.create(
                kpi=kpi,
                date=date,
                value=value,
                notes=notes,
                entered_by=request.user,
                source='manual'
            )
            action = 'added'
        
        log_user_action(
            request, 'create' if action == 'added' else 'update', 
            'KPIDataPoint', f'{kpi_id}:{date}', 
            f'{action.title()} data point for {kpi.name}'
        )
        
        messages.success(request, f'Data point {action} successfully.')
    
    return redirect('kpis:detail', pk=kpi_id)


@login_required
def kpi_chart_data(request, kpi_id):
    """
    Get chart data for a KPI (AJAX endpoint).
    """
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant found'}, status=404)
    
    try:
        kpi = SmartKPI.objects.get(id=kpi_id, tenant=tenant)
    except SmartKPI.DoesNotExist:
        return JsonResponse({'error': 'KPI not found'}, status=404)
    
    # Get time range from request
    days = int(request.GET.get('days', 30))
    
    # Get trend data
    trend_data = kpi.get_trend_data(days=days)
    
    # Prepare chart configuration
    chart_config = {
        'type': kpi.chart_type,
        'data': {
            'labels': [point['date'] for point in trend_data],
            'datasets': [
                {
                    'label': kpi.name,
                    'data': [point['value'] for point in trend_data],
                    'borderColor': kpi.category.color if kpi.category else '#007bff',
                    'backgroundColor': f"{kpi.category.color}20" if kpi.category else '#007bff20',
                    'fill': kpi.chart_type == 'area'
                }
            ]
        },
        'options': {
            'responsive': True,
            'scales': {
                'y': {
                    'beginAtZero': False,
                    'title': {
                        'display': True,
                        'text': kpi.unit or 'Value'
                    }
                }
            },
            'plugins': {
                'title': {
                    'display': True,
                    'text': kpi.name
                },
                'legend': {
                    'display': False
                }
            }
        }
    }
    
    # Add target line if target is set
    if kpi.target_value and trend_data:
        chart_config['data']['datasets'].append({
            'label': 'Target',
            'data': [float(kpi.target_value)] * len(trend_data),
            'borderColor': '#28a745',
            'borderDash': [5, 5],
            'fill': False,
            'pointRadius': 0
        })
    
    return JsonResponse({
        'chart_config': chart_config,
        'current_value': float(kpi.get_latest_value() or 0),
        'target_value': float(kpi.target_value or 0),
        'performance_status': kpi.calculate_performance_status(),
        'unit': kpi.unit
    })


@login_required
def kpi_dashboard_view(request, dashboard_id=None):
    """
    Display a custom KPI dashboard.
    """
    tenant = get_current_tenant()
    if not tenant:
        messages.error(request, 'No tenant found.')
        return redirect('dashboard:home')
    
    if dashboard_id:
        dashboard = get_object_or_404(
            KPIDashboard, 
            id=dashboard_id, 
            tenant=tenant
        )
        
        # Check permissions
        if not dashboard.is_public and dashboard.owner != request.user:
            if request.user not in dashboard.shared_with.all():
                messages.error(request, 'You do not have access to this dashboard.')
                return redirect('kpis:list')
    else:
        # Get or create default dashboard
        dashboard, created = KPIDashboard.objects.get_or_create(
            tenant=tenant,
            owner=request.user,
            name='My Dashboard',
            defaults={
                'description': 'Personal KPI dashboard',
                'layout': {'columns': 12, 'row_height': 150}
            }
        )
        
        if created:
            # Add featured KPIs to the dashboard
            featured_kpis = SmartKPI.objects.filter(
                tenant=tenant, 
                is_featured=True, 
                is_active=True
            )[:6]  # Limit to 6 KPIs
            
            for i, kpi in enumerate(featured_kpis):
                row = i // 3
                col = (i % 3) * 4  # 4 columns per KPI (12/3)
                
                DashboardKPI.objects.create(
                    dashboard=dashboard,
                    kpi=kpi,
                    position_x=col,
                    position_y=row,
                    width=4,
                    height=4
                )
    
    # Get dashboard KPIs
    dashboard_kpis = DashboardKPI.objects.filter(
        dashboard=dashboard
    ).select_related('kpi', 'kpi__category').order_by('position_y', 'position_x')
    
    context = {
        'dashboard': dashboard,
        'dashboard_kpis': dashboard_kpis,
        'can_edit': dashboard.owner == request.user,
    }
    
    return render(request, 'kpis/dashboard.html', context)


@login_required
def acknowledge_alert(request, alert_id):
    """
    Acknowledge a KPI alert.
    """
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant found'})
    
    try:
        alert = KPIAlert.objects.get(
            id=alert_id, 
            kpi__tenant=tenant
        )
    except KPIAlert.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Alert not found'})
    
    alert.acknowledge(request.user)
    
    log_user_action(
        request, 'update', 'KPIAlert', 
        str(alert.id), f'Acknowledged alert: {alert.title}'
    )
    
    return JsonResponse({'success': True})


@login_required
def kpi_analytics_data(request):
    """
    Get analytics data for all KPIs (AJAX endpoint).
    """
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant found'}, status=404)
    
    kpis = SmartKPI.objects.filter(tenant=tenant, is_active=True)
    
    analytics_data = {
        'total_kpis': kpis.count(),
        'categories': [],
        'performance_summary': {
            'excellent': 0,
            'good': 0,
            'warning': 0,
            'critical': 0,
            'unknown': 0
        },
        'recent_alerts': []
    }
    
    # Category breakdown
    categories = KPICategory.objects.filter(tenant=tenant, is_active=True)
    for category in categories:
        category_kpis = kpis.filter(category=category)
        analytics_data['categories'].append({
            'name': category.name,
            'count': category_kpis.count(),
            'color': category.color
        })
    
    # Performance summary
    for kpi in kpis:
        status = kpi.calculate_performance_status()
        analytics_data['performance_summary'][status] += 1
    
    # Recent alerts
    recent_alerts = KPIAlert.objects.filter(
        kpi__tenant=tenant,
        is_resolved=False
    ).select_related('kpi').order_by('-created_at')[:10]
    
    for alert in recent_alerts:
        analytics_data['recent_alerts'].append({
            'id': str(alert.id),
            'kpi_name': alert.kpi.name,
            'title': alert.title,
            'severity': alert.severity,
            'created_at': alert.created_at.isoformat(),
            'is_acknowledged': alert.is_acknowledged
        })
    
    return JsonResponse(analytics_data)


class KPICategoryCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new KPI category.
    """
    model = KPICategory
    template_name = 'kpis/category_form.html'
    fields = ['name', 'category_type', 'description', 'color', 'icon']
    success_url = reverse_lazy('kpis:list')
    
    def form_valid(self, form):
        tenant = get_current_tenant()
        if not tenant:
            messages.error(self.request, 'No tenant found.')
            return redirect('kpis:list')
        
        form.instance.tenant = tenant
        response = super().form_valid(form)
        
        log_user_action(
            self.request, 'create', 'KPICategory', 
            str(self.object.id), f'Created KPI category: {self.object.name}'
        )
        
        messages.success(self.request, f'KPI category "{self.object.name}" created successfully.')
        return response
