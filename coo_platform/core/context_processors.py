"""
Context processors for adding common data to templates.
"""
from .utils import get_dashboard_context
from tenants.middleware import get_current_tenant


def tenant_context(request):
    """
    Add tenant and common dashboard context to all templates.
    """
    user = request.user if hasattr(request, 'user') else None
    tenant = get_current_tenant()
    
    context = get_dashboard_context(user, tenant)
    
    # Add current time for templates
    from django.utils import timezone
    context['current_time'] = timezone.now()
    
    return context


def navigation_context(request):
    """
    Add navigation-related context.
    """
    context = {}
    
    if hasattr(request, 'user') and request.user.is_authenticated:
        # Count various items for navigation badges
        try:
            # Projects count for current user/tenant
            from projects.models import Project
            tenant = get_current_tenant()
            if tenant:
                context['projects_count'] = Project.objects.filter(
                    tenant=tenant
                ).count()
            
            # Tasks assigned to user
            from projects.models import Task
            context['my_tasks_count'] = Task.objects.filter(
                assigned_to=request.user,
                project__tenant=tenant
            ).exclude(status='completed').count() if tenant else 0
            
            # Critical alerts
            from kpis.models import KPIAlert
            context['critical_alerts_count'] = KPIAlert.objects.filter(
                kpi__tenant=tenant,
                severity='critical',
                is_resolved=False
            ).count() if tenant else 0
            
        except Exception:
            # If models aren't available yet (during migrations), ignore
            pass
    
    return context