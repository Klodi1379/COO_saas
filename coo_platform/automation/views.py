"""
Views for automation management.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Q
from .models import AutomationRule, AutomationAction, AutomationLog
from core.views import DashboardMixin
from core.utils import log_user_action
from tenants.middleware import get_current_tenant


class AutomationRuleListView(DashboardMixin, LoginRequiredMixin, ListView):
    """
    List all automation rules for the current tenant.
    """
    model = AutomationRule
    template_name = 'automation/automationrule_list.html'
    context_object_name = 'rules'
    paginate_by = 20
    
    def get_queryset(self):
        tenant = get_current_tenant()
        if not tenant:
            return AutomationRule.objects.none()
        
        queryset = AutomationRule.objects.filter(tenant=tenant).select_related('created_by')
        
        # Filter by status if specified
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by trigger type
        trigger_type = self.request.GET.get('trigger_type')
        if trigger_type:
            queryset = queryset.filter(trigger_type=trigger_type)
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )
        
        # Sort by parameter
        sort_by = self.request.GET.get('sort', '-created_at')
        if sort_by in ['name', '-name', 'status', '-status', 'created_at', '-created_at']:
            queryset = queryset.order_by(sort_by)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context.update({
            'status_choices': AutomationRule.STATUS_CHOICES,
            'trigger_types': AutomationRule.TRIGGER_TYPES,
            'current_filters': {
                'status': self.request.GET.get('status', ''),
                'trigger_type': self.request.GET.get('trigger_type', ''),
                'search': self.request.GET.get('search', ''),
                'sort': self.request.GET.get('sort', '-created_at'),
            }
        })
        
        return context


class AutomationRuleDetailView(DashboardMixin, LoginRequiredMixin, DetailView):
    """
    Detailed view of a single automation rule.
    """
    model = AutomationRule
    template_name = 'automation/automationrule_detail.html'
    context_object_name = 'rule'
    
    def get_queryset(self):
        tenant = get_current_tenant()
        if not tenant:
            return AutomationRule.objects.none()
        return AutomationRule.objects.filter(tenant=tenant)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rule = self.object
        
        # Get rule actions
        actions = rule.actions.all().order_by('order')
        
        # Get recent execution logs
        recent_logs = rule.logs.order_by('-created_at')[:20]
        
        # Get execution statistics
        log_stats = rule.logs.aggregate(
            total=Count('id'),
            success=Count('id', filter=Q(status='success')),
            error=Count('id', filter=Q(status='error')),
            partial=Count('id', filter=Q(status='partial'))
        )
        
        context.update({
            'actions': actions,
            'recent_logs': recent_logs,
            'log_stats': log_stats,
            'can_edit': rule.created_by == self.request.user,
        })
        
        return context


@login_required
def toggle_rule_status(request, rule_id):
    """
    Toggle automation rule enabled/disabled status.
    """
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant found'})
    
    try:
        rule = AutomationRule.objects.get(id=rule_id, tenant=tenant)
    except AutomationRule.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rule not found'})
    
    # Check permissions
    if rule.created_by != request.user and request.user not in rule.team_access.all():
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    # Toggle status
    rule.is_enabled = not rule.is_enabled
    rule.save(update_fields=['is_enabled'])
    
    log_user_action(
        request, 'update', 'AutomationRule', 
        str(rule.id), f'{"Enabled" if rule.is_enabled else "Disabled"} rule: {rule.name}'
    )
    
    return JsonResponse({
        'success': True,
        'is_enabled': rule.is_enabled
    })


@login_required
def execute_rule_manually(request, rule_id):
    """
    Manually execute an automation rule.
    """
    tenant = get_current_tenant()
    if not tenant:
        messages.error(request, 'No tenant found.')
        return redirect('automation:list')
    
    try:
        rule = AutomationRule.objects.get(id=rule_id, tenant=tenant)
    except AutomationRule.DoesNotExist:
        messages.error(request, 'Rule not found.')
        return redirect('automation:list')
    
    # Check permissions
    if rule.created_by != request.user and request.user not in rule.team_access.all():
        messages.error(request, 'Permission denied.')
        return redirect('automation:detail', pk=rule_id)
    
    # Execute the rule
    try:
        success = rule.execute()
        if success:
            messages.success(request, f'Rule "{rule.name}" executed successfully.')
        else:
            messages.warning(request, f'Rule "{rule.name}" executed with some failures.')
        
        log_user_action(
            request, 'execute', 'AutomationRule', 
            str(rule.id), f'Manually executed rule: {rule.name}'
        )
        
    except Exception as e:
        messages.error(request, f'Failed to execute rule: {str(e)}')
    
    return redirect('automation:detail', pk=rule_id)


@login_required
def automation_analytics(request):
    """
    Get automation analytics data (AJAX endpoint).
    """
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant found'}, status=404)
    
    rules = AutomationRule.objects.filter(tenant=tenant)
    
    analytics_data = {
        'total_rules': rules.count(),
        'active_rules': rules.filter(is_enabled=True, status='active').count(),
        'total_executions': sum(rule.execution_count for rule in rules),
        'rule_types': [],
        'execution_stats': {
            'success': 0,
            'error': 0,
            'partial': 0,
        },
        'recent_activity': []
    }
    
    # Rule types breakdown
    from django.db.models import Count
    rule_type_stats = rules.values('trigger_type').annotate(count=Count('id'))
    for stat in rule_type_stats:
        trigger_type_display = dict(AutomationRule.TRIGGER_TYPES).get(
            stat['trigger_type'], stat['trigger_type']
        )
        analytics_data['rule_types'].append({
            'type': trigger_type_display,
            'count': stat['count']
        })
    
    # Execution statistics from logs
    from datetime import datetime, timedelta
    recent_logs = AutomationLog.objects.filter(
        rule__tenant=tenant,
        created_at__gte=datetime.now() - timedelta(days=30)
    )
    
    log_stats = recent_logs.values('status').annotate(count=Count('id'))
    for stat in log_stats:
        analytics_data['execution_stats'][stat['status']] = stat['count']
    
    # Recent activity
    recent_activity = recent_logs.select_related('rule').order_by('-created_at')[:10]
    for log in recent_activity:
        analytics_data['recent_activity'].append({
            'rule_name': log.rule.name,
            'status': log.status,
            'message': log.message[:100],
            'created_at': log.created_at.isoformat()
        })
    
    return JsonResponse(analytics_data)


class AutomationRuleCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new automation rule.
    """
    model = AutomationRule
    template_name = 'automation/rule_form.html'
    fields = [
        'name', 'description', 'trigger_type', 'trigger_config',
        'priority', 'run_once', 'max_executions', 'start_date', 'end_date'
    ]
    
    def form_valid(self, form):
        tenant = get_current_tenant()
        if not tenant:
            messages.error(self.request, 'No tenant found.')
            return redirect('automation:list')
        
        form.instance.tenant = tenant
        form.instance.created_by = self.request.user
        form.instance.status = 'draft'  # Start as draft
        
        response = super().form_valid(form)
        
        log_user_action(
            self.request, 'create', 'AutomationRule', 
            str(self.object.id), f'Created automation rule: {self.object.name}'
        )
        
        messages.success(self.request, f'Automation rule "{self.object.name}" created successfully.')
        return response
    
    def get_success_url(self):
        return self.object.get_absolute_url()


@login_required
def create_automation_action(request, rule_id):
    """
    Create a new action for an automation rule.
    """
    tenant = get_current_tenant()
    if not tenant:
        messages.error(request, 'No tenant found.')
        return redirect('automation:list')
    
    try:
        rule = AutomationRule.objects.get(id=rule_id, tenant=tenant)
    except AutomationRule.DoesNotExist:
        messages.error(request, 'Rule not found.')
        return redirect('automation:list')
    
    # Check permissions
    if rule.created_by != request.user and request.user not in rule.team_access.all():
        messages.error(request, 'Permission denied.')
        return redirect('automation:detail', pk=rule_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        action_type = request.POST.get('action_type')
        description = request.POST.get('description', '')
        order = request.POST.get('order', 1)
        
        if not name or not action_type:
            messages.error(request, 'Name and action type are required.')
            return redirect('automation:detail', pk=rule_id)
        
        # Create the action
        action = AutomationAction.objects.create(
            rule=rule,
            name=name,
            action_type=action_type,
            description=description,
            order=int(order),
            action_config={}  # Will be configured later
        )
        
        log_user_action(
            request, 'create', 'AutomationAction', 
            str(action.id), f'Created action: {action.name} for rule: {rule.name}'
        )
        
        messages.success(request, f'Action "{action.name}" created successfully.')
    
    return redirect('automation:detail', pk=rule_id)
