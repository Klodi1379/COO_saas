"""
Admin configuration for project models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    ProjectCategory, Project, ProjectMembership, 
    Task, TaskComment, ProjectUpdate
)


@admin.register(ProjectCategory)
class ProjectCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'project_count', 'color_display', 'is_active', 'created_at')
    list_filter = ('tenant', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def project_count(self, obj):
        count = obj.projects.count()
        if count > 0:
            url = reverse('admin:projects_project_changelist') + f'?category__id={obj.id}'
            return format_html('<a href="{}">{} projects</a>', url, count)
        return '0 projects'
    project_count.short_description = 'Projects'
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
            obj.color
        )
    color_display.short_description = 'Color'


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 0
    raw_id_fields = ('user',)
    readonly_fields = ('joined_date', 'created_at')


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ('title', 'assigned_to', 'status', 'priority', 'due_date')
    readonly_fields = ('created_at',)
    show_change_link = True


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'tenant', 'status', 'priority', 'project_manager', 
        'progress_display', 'budget_display', 'created_at'
    )
    list_filter = (
        'status', 'priority', 'tenant', 'category', 
        'created_at', 'start_date', 'target_end_date'
    )
    search_fields = ('name', 'description', 'project_manager__username')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'progress_percentage',
        'budget_remaining', 'budget_utilization', 'is_overdue', 'days_remaining'
    )
    raw_id_fields = ('project_manager',)
    filter_horizontal = ()
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'category', 'tags')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'progress_percentage')
        }),
        ('Team & Management', {
            'fields': ('project_manager',)
        }),
        ('Timeline', {
            'fields': ('start_date', 'target_end_date', 'actual_end_date', 'days_remaining', 'is_overdue')
        }),
        ('Budget & Resources', {
            'fields': ('budget_allocated', 'budget_spent', 'budget_remaining', 'budget_utilization')
        }),
        ('Files & Documentation', {
            'fields': ('project_charter',)
        }),
        ('Custom Data', {
            'fields': ('custom_fields',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ProjectMembershipInline, TaskInline]
    
    actions = ['mark_active', 'mark_completed', 'mark_on_hold']
    
    def progress_display(self, obj):
        if obj.progress_percentage >= 100:
            color = 'green'
        elif obj.progress_percentage >= 75:
            color = 'blue'
        elif obj.progress_percentage >= 50:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">'
            '{}%</div></div>',
            obj.progress_percentage, color, obj.progress_percentage
        )
    progress_display.short_description = 'Progress'
    
    def budget_display(self, obj):
        if obj.budget_allocated:
            spent_pct = obj.budget_utilization
            if spent_pct > 100:
                color = 'red'
            elif spent_pct > 80:
                color = 'orange'
            else:
                color = 'green'
            
            return format_html(
                '<span style="color: {};">${:,.0f} / ${:,.0f} ({:.1f}%)</span>',
                color, obj.budget_spent, obj.budget_allocated, spent_pct
            )
        return format_html('<span style="color: gray;">No budget set</span>')
    budget_display.short_description = 'Budget'
    
    def mark_active(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} projects marked as active.')
    mark_active.short_description = 'Mark as Active'
    
    def mark_completed(self, request, queryset):
        from django.utils import timezone
        updated = 0
        for project in queryset:
            project.status = 'completed'
            project.progress_percentage = 100
            if not project.actual_end_date:
                project.actual_end_date = timezone.now().date()
            project.save()
            updated += 1
        self.message_user(request, f'{updated} projects marked as completed.')
    mark_completed.short_description = 'Mark as Completed'
    
    def mark_on_hold(self, request, queryset):
        updated = queryset.update(status='on_hold')
        self.message_user(request, f'{updated} projects marked as on hold.')
    mark_on_hold.short_description = 'Mark as On Hold'


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'role', 'is_active', 'joined_date')
    list_filter = ('role', 'is_active', 'joined_date', 'project__tenant')
    search_fields = ('user__username', 'user__email', 'project__name')
    raw_id_fields = ('user', 'project')
    readonly_fields = ('joined_date', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('project', 'user', 'role', 'is_active', 'joined_date')
        }),
        ('Permissions', {
            'fields': ('can_edit_project', 'can_manage_tasks', 'can_invite_members')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class TaskCommentInline(admin.TabularInline):
    model = TaskComment
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('author', 'content', 'attachment', 'created_at')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'project', 'assigned_to', 'status', 'priority', 
        'due_date', 'progress_display', 'created_at'
    )
    list_filter = (
        'status', 'priority', 'project__tenant', 'project', 
        'assigned_to', 'due_date', 'created_at'
    )
    search_fields = ('title', 'description', 'project__name', 'assigned_to__username')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'started_at', 'completed_at',
        'is_overdue', 'can_start'
    )
    raw_id_fields = ('project', 'assigned_to', 'created_by')
    filter_horizontal = ('depends_on',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('project', 'title', 'description', 'tags')
        }),
        ('Assignment & Status', {
            'fields': ('assigned_to', 'created_by', 'status', 'priority')
        }),
        ('Timeline', {
            'fields': ('due_date', 'started_at', 'completed_at', 'is_overdue')
        }),
        ('Estimation & Tracking', {
            'fields': ('estimated_hours', 'actual_hours')
        }),
        ('Dependencies', {
            'fields': ('depends_on', 'can_start')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TaskCommentInline]
    
    actions = ['mark_in_progress', 'mark_completed', 'mark_blocked']
    
    def progress_display(self, obj):
        if obj.status == 'completed':
            return format_html('<span style="color: green;">✓ Completed</span>')
        elif obj.status == 'in_progress':
            return format_html('<span style="color: blue;">⏳ In Progress</span>')
        elif obj.status == 'blocked':
            return format_html('<span style="color: red;">🚫 Blocked</span>')
        elif obj.status == 'review':
            return format_html('<span style="color: orange;">👁 Review</span>')
        else:
            return format_html('<span style="color: gray;">📝 To Do</span>')
    progress_display.short_description = 'Status'
    
    def mark_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f'{updated} tasks marked as in progress.')
    mark_in_progress.short_description = 'Mark as In Progress'
    
    def mark_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} tasks marked as completed.')
    mark_completed.short_description = 'Mark as Completed'
    
    def mark_blocked(self, request, queryset):
        updated = queryset.update(status='blocked')
        self.message_user(request, f'{updated} tasks marked as blocked.')
    mark_blocked.short_description = 'Mark as Blocked'


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'author', 'content_preview', 'created_at')
    list_filter = ('created_at', 'task__project__tenant')
    search_fields = ('content', 'task__title', 'author__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields = ('task', 'author')
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'


@admin.register(ProjectUpdate)
class ProjectUpdateAdmin(admin.ModelAdmin):
    list_display = ('project', 'update_type', 'title', 'author', 'created_at')
    list_filter = ('update_type', 'created_at', 'project__tenant')
    search_fields = ('title', 'content', 'project__name', 'author__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields = ('project', 'author')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('project', 'author', 'update_type', 'title', 'content')
        }),
        ('Metrics Snapshot', {
            'fields': ('progress_at_update', 'budget_spent_at_update')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
