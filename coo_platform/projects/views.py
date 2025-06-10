"""
Views for project management.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.urls import reverse_lazy
from .models import (
    Project, ProjectCategory, Task, ProjectMembership, 
    TaskComment, ProjectUpdate
)
from core.views import DashboardMixin
from core.utils import log_user_action, create_notification
from tenants.middleware import get_current_tenant


class ProjectListView(DashboardMixin, LoginRequiredMixin, ListView):
    """
    List all projects for the current tenant.
    """
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'
    paginate_by = 20
    
    def get_queryset(self):
        tenant = get_current_tenant()
        if not tenant:
            return Project.objects.none()
        
        queryset = Project.objects.filter(tenant=tenant).select_related(
            'project_manager', 'category'
        ).prefetch_related('team_members')
        
        # Filter by status if specified
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by category if specified
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search) |
                Q(project_manager__username__icontains=search)
            )
        
        # Sort by parameter
        sort_by = self.request.GET.get('sort', '-created_at')
        if sort_by in ['name', '-name', 'status', '-status', 'priority', '-priority', 
                       'created_at', '-created_at', 'target_end_date', '-target_end_date']:
            queryset = queryset.order_by(sort_by)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant()
        
        if tenant:
            context.update({
                'categories': ProjectCategory.objects.filter(tenant=tenant, is_active=True),
                'status_choices': Project.STATUS_CHOICES,
                'current_filters': {
                    'status': self.request.GET.get('status', ''),
                    'category': self.request.GET.get('category', ''),
                    'search': self.request.GET.get('search', ''),
                    'sort': self.request.GET.get('sort', '-created_at'),
                }
            })
        
        return context


class ProjectDetailView(DashboardMixin, LoginRequiredMixin, DetailView):
    """
    Detailed view of a single project.
    """
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'
    
    def get_queryset(self):
        tenant = get_current_tenant()
        if not tenant:
            return Project.objects.none()
        return Project.objects.filter(tenant=tenant)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        
        # Get project tasks with status breakdown
        tasks = project.tasks.all()
        task_stats = tasks.aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            in_progress=Count('id', filter=Q(status='in_progress')),
            todo=Count('id', filter=Q(status='todo')),
            blocked=Count('id', filter=Q(status='blocked'))
        )
        
        # Get recent updates
        recent_updates = project.updates.select_related('author')[:10]
        
        # Get team members
        team_members = project.get_team_members()
        
        # Check user permissions
        user_membership = ProjectMembership.objects.filter(
            project=project,
            user=self.request.user,
            is_active=True
        ).first()
        
        context.update({
            'tasks': tasks.order_by('priority', 'due_date'),
            'task_stats': task_stats,
            'recent_updates': recent_updates,
            'team_members': team_members,
            'user_membership': user_membership,
            'can_edit': (
                user_membership and user_membership.can_edit_project
            ) or self.request.user == project.project_manager,
        })
        
        return context


class ProjectCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new project.
    """
    model = Project
    template_name = 'projects/project_form.html'
    fields = [
        'name', 'description', 'category', 'status', 'priority',
        'project_manager', 'start_date', 'target_end_date',
        'budget_allocated', 'tags'
    ]
    
    def form_valid(self, form):
        tenant = get_current_tenant()
        if not tenant:
            messages.error(self.request, 'No tenant found.')
            return redirect('projects:list')
        
        form.instance.tenant = tenant
        response = super().form_valid(form)
        
        # Add creator as project member
        ProjectMembership.objects.create(
            project=self.object,
            user=self.request.user,
            role='manager',
            can_edit_project=True,
            can_manage_tasks=True,
            can_invite_members=True
        )
        
        log_user_action(
            self.request, 'create', 'Project', 
            str(self.object.id), f'Created project: {self.object.name}'
        )
        
        messages.success(self.request, f'Project "{self.object.name}" created successfully.')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant()
        
        if tenant:
            context['categories'] = ProjectCategory.objects.filter(
                tenant=tenant, is_active=True
            )
        
        return context


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    """
    Update an existing project.
    """
    model = Project
    template_name = 'projects/project_form.html'
    fields = [
        'name', 'description', 'category', 'status', 'priority',
        'project_manager', 'start_date', 'target_end_date', 'actual_end_date',
        'budget_allocated', 'budget_spent', 'progress_percentage', 'tags'
    ]
    
    def get_queryset(self):
        tenant = get_current_tenant()
        if not tenant:
            return Project.objects.none()
        return Project.objects.filter(tenant=tenant)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        log_user_action(
            self.request, 'update', 'Project', 
            str(self.object.id), f'Updated project: {self.object.name}'
        )
        
        messages.success(self.request, f'Project "{self.object.name}" updated successfully.')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant()
        
        if tenant:
            context['categories'] = ProjectCategory.objects.filter(
                tenant=tenant, is_active=True
            )
        
        return context


@login_required
def create_task(request, project_id):
    """
    Create a new task for a project.
    """
    tenant = get_current_tenant()
    if not tenant:
        messages.error(request, 'No tenant found.')
        return redirect('projects:list')
    
    project = get_object_or_404(Project, id=project_id, tenant=tenant)
    
    # Check permissions
    user_membership = ProjectMembership.objects.filter(
        project=project,
        user=request.user,
        is_active=True
    ).first()
    
    if not user_membership or not user_membership.can_manage_tasks:
        messages.error(request, 'You do not have permission to create tasks.')
        return redirect('projects:detail', pk=project_id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        assigned_to_id = request.POST.get('assigned_to')
        priority = request.POST.get('priority', 'medium')
        due_date = request.POST.get('due_date')
        estimated_hours = request.POST.get('estimated_hours')
        
        if not title:
            messages.error(request, 'Task title is required.')
            return redirect('projects:detail', pk=project_id)
        
        # Create task
        task_data = {
            'project': project,
            'title': title,
            'description': description,
            'created_by': request.user,
            'priority': priority,
        }
        
        if assigned_to_id:
            try:
                assigned_to = project.team_members.get(id=assigned_to_id)
                task_data['assigned_to'] = assigned_to
            except:
                pass
        
        if due_date:
            from datetime import datetime
            try:
                task_data['due_date'] = datetime.strptime(due_date, '%Y-%m-%d')
            except:
                pass
        
        if estimated_hours:
            try:
                task_data['estimated_hours'] = float(estimated_hours)
            except:
                pass
        
        task = Task.objects.create(**task_data)
        
        # Send notification to assigned user
        if task.assigned_to and task.assigned_to != request.user:
            create_notification(
                recipient=task.assigned_to,
                notification_type='task_assigned',
                title='New task assigned',
                message=f'You have been assigned a new task: {task.title}',
                action_url=task.get_absolute_url(),
                action_label='View Task'
            )
        
        log_user_action(
            request, 'create', 'Task', 
            str(task.id), f'Created task: {task.title}'
        )
        
        messages.success(request, f'Task "{task.title}" created successfully.')
    
    return redirect('projects:detail', pk=project_id)


@login_required
def update_task_status(request, task_id):
    """
    Update task status (AJAX endpoint).
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant found'})
    
    try:
        task = Task.objects.get(id=task_id, project__tenant=tenant)
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'})
    
    # Check permissions
    user_membership = ProjectMembership.objects.filter(
        project=task.project,
        user=request.user,
        is_active=True
    ).first()
    
    if not user_membership and task.assigned_to != request.user:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    new_status = request.POST.get('status')
    if new_status not in dict(Task.STATUS_CHOICES):
        return JsonResponse({'success': False, 'error': 'Invalid status'})
    
    old_status = task.status
    task.status = new_status
    task.save()
    
    # Send notification for status changes
    if task.assigned_to and task.assigned_to != request.user:
        create_notification(
            recipient=task.assigned_to,
            notification_type='info',
            title='Task status updated',
            message=f'Task "{task.title}" status changed from {old_status} to {new_status}',
            action_url=task.get_absolute_url(),
            action_label='View Task'
        )
    
    log_user_action(
        request, 'update', 'Task', 
        str(task.id), f'Changed status from {old_status} to {new_status}'
    )
    
    return JsonResponse({
        'success': True,
        'new_status': new_status,
        'project_progress': task.project.progress_percentage
    })


@login_required
def project_dashboard_data(request, project_id):
    """
    Get project dashboard data (AJAX endpoint).
    """
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant found'}, status=404)
    
    try:
        project = Project.objects.get(id=project_id, tenant=tenant)
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    
    # Task status breakdown
    task_stats = project.tasks.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        in_progress=Count('id', filter=Q(status='in_progress')),
        todo=Count('id', filter=Q(status='todo')),
        blocked=Count('id', filter=Q(status='blocked'))
    )
    
    # Budget information
    budget_data = {
        'allocated': float(project.budget_allocated or 0),
        'spent': float(project.budget_spent),
        'remaining': float(project.budget_remaining or 0),
        'utilization': project.budget_utilization
    }
    
    # Timeline information
    timeline_data = {
        'start_date': project.start_date.isoformat() if project.start_date else None,
        'target_end_date': project.target_end_date.isoformat() if project.target_end_date else None,
        'actual_end_date': project.actual_end_date.isoformat() if project.actual_end_date else None,
        'days_remaining': project.days_remaining,
        'is_overdue': project.is_overdue
    }
    
    return JsonResponse({
        'project': {
            'name': project.name,
            'status': project.status,
            'priority': project.priority,
            'progress': project.progress_percentage
        },
        'tasks': task_stats,
        'budget': budget_data,
        'timeline': timeline_data
    })
