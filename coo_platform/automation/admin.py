"""
Admin configuration for automation models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    AutomationRule, AutomationAction, AutomationLog, AutomationSchedule
)


class AutomationActionInline(admin.TabularInline):
    model = AutomationAction
    extra = 0
    fields = ('name', 'action_type', 'is_enabled', 'order', 'delay_seconds')
    readonly_fields = ('created_at',)


class AutomationScheduleInline(admin.StackedInline):
    model = AutomationSchedule
    extra = 0
    readonly_fields = ('last_run', 'next_run')


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'tenant', 'trigger_type', 'status', 'is_enabled',
        'execution_count', 'last_triggered', 'created_by'
    )
    list_filter = (
        'status', 'trigger_type', 'is_enabled', 'tenant',
        'created_at', 'last_triggered'
    )
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = (
        'id', 'execution_count', 'last_triggered', 'created_at', 'updated_at'
    )
    raw_id_fields = ('created_by',)
    filter_horizontal = ('team_access',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'status', 'created_by')
        }),
        ('Trigger Configuration', {
            'fields': ('trigger_type', 'trigger_config')
        }),
        ('Execution Settings', {
            'fields': (
                'is_enabled', 'run_once', 'max_executions', 'execution_count',
                'priority', 'timeout_seconds'
            )
        }),
        ('Timing & Access', {
            'fields': ('start_date', 'end_date', 'last_triggered', 'team_access')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [AutomationActionInline, AutomationScheduleInline]
    
    actions = ['enable_rules', 'disable_rules', 'reset_execution_count']
    
    def enable_rules(self, request, queryset):
        updated = queryset.update(is_enabled=True)
        self.message_user(request, f'{updated} rules enabled.')
    enable_rules.short_description = 'Enable selected rules'
    
    def disable_rules(self, request, queryset):
        updated = queryset.update(is_enabled=False)
        self.message_user(request, f'{updated} rules disabled.')
    disable_rules.short_description = 'Disable selected rules'
    
    def reset_execution_count(self, request, queryset):
        updated = queryset.update(execution_count=0)
        self.message_user(request, f'{updated} execution counts reset.')
    reset_execution_count.short_description = 'Reset execution count'


@admin.register(AutomationAction)
class AutomationActionAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'rule', 'action_type', 'is_enabled', 
        'order', 'delay_seconds', 'max_retries'
    )
    list_filter = (
        'action_type', 'is_enabled', 'rule__tenant', 
        'continue_on_failure', 'created_at'
    )
    search_fields = ('name', 'description', 'rule__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields = ('rule',)
    list_editable = ('is_enabled', 'order')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('rule', 'name', 'description', 'action_type')
        }),
        ('Configuration', {
            'fields': ('action_config',)
        }),
        ('Execution Settings', {
            'fields': (
                'is_enabled', 'order', 'continue_on_failure',
                'delay_seconds', 'max_retries', 'retry_delay_seconds'
            )
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('rule')


@admin.register(AutomationLog)
class AutomationLogAdmin(admin.ModelAdmin):
    list_display = (
        'rule', 'action', 'status_display', 'message_preview', 
        'execution_time_ms', 'created_at'
    )
    list_filter = (
        'status', 'rule__tenant', 'rule__trigger_type', 'created_at'
    )
    search_fields = ('message', 'rule__name', 'action__name')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'execution_time_ms'
    )
    raw_id_fields = ('rule', 'action')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Execution Information', {
            'fields': ('rule', 'action', 'status', 'message', 'execution_time_ms')
        }),
        ('Data', {
            'fields': ('trigger_data', 'result_data'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_display(self, obj):
        colors = {
            'success': 'green',
            'error': 'red',
            'partial': 'orange',
            'skipped': 'gray'
        }
        
        icons = {
            'success': '✅',
            'error': '❌',
            'partial': '⚠️',
            'skipped': '⏭️'
        }
        
        color = colors.get(obj.status, 'gray')
        icon = icons.get(obj.status, '❓')
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def message_preview(self, obj):
        preview = obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
        return preview
    message_preview.short_description = 'Message'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AutomationSchedule)
class AutomationScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'rule', 'frequency', 'start_time', 'timezone',
        'last_run', 'next_run', 'is_active'
    )
    list_filter = (
        'frequency', 'is_active', 'timezone', 'rule__tenant', 'created_at'
    )
    search_fields = ('rule__name', 'cron_expression')
    readonly_fields = (
        'id', 'last_run', 'next_run', 'created_at', 'updated_at'
    )
    raw_id_fields = ('rule',)
    list_editable = ('is_active',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('rule', 'frequency', 'start_time', 'timezone', 'is_active')
        }),
        ('Date Constraints', {
            'fields': ('start_date', 'end_date')
        }),
        ('Custom Scheduling', {
            'fields': ('cron_expression',),
            'description': 'Only used when frequency is "custom"'
        }),
        ('Execution Tracking', {
            'fields': ('last_run', 'next_run')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['calculate_next_runs', 'activate_schedules', 'deactivate_schedules']
    
    def calculate_next_runs(self, request, queryset):
        updated = 0
        for schedule in queryset:
            schedule.calculate_next_run()
            updated += 1
        self.message_user(request, f'{updated} next run times calculated.')
    calculate_next_runs.short_description = 'Recalculate next run times'
    
    def activate_schedules(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} schedules activated.')
    activate_schedules.short_description = 'Activate selected schedules'
    
    def deactivate_schedules(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} schedules deactivated.')
    deactivate_schedules.short_description = 'Deactivate selected schedules'
