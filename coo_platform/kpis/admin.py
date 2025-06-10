"""
Admin configuration for KPI models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from .models import (
    KPICategory, SmartKPI, KPIDataPoint, KPIAlert, 
    KPIDashboard, DashboardKPI
)


@admin.register(KPICategory)
class KPICategoryAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category_type', 'tenant', 'kpi_count_display', 
        'color_display', 'is_active', 'display_order'
    )
    list_filter = ('category_type', 'tenant', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('display_order', 'is_active')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'category_type', 'description')
        }),
        ('Display Settings', {
            'fields': ('color', 'icon', 'display_order', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def kpi_count_display(self, obj):
        count = obj.kpi_count
        if count > 0:
            url = reverse('admin:kpis_smartkpi_changelist') + f'?category__id={obj.id}'
            return format_html('<a href="{}">{} KPIs</a>', url, count)
        return '0 KPIs'
    kpi_count_display.short_description = 'KPIs'
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; border-radius: 3px;"></div>',
            obj.color
        )
    color_display.short_description = 'Color'


class KPIDataPointInline(admin.TabularInline):
    model = KPIDataPoint
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('date', 'value', 'source', 'entered_by', 'notes', 'confidence_level')
    ordering = ['-date']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('entered_by')


class KPIAlertInline(admin.TabularInline):
    model = KPIAlert
    extra = 0
    readonly_fields = ('created_at', 'acknowledged_at', 'resolved_at')
    fields = ('alert_type', 'severity', 'title', 'is_acknowledged', 'is_resolved')
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_resolved=False)


@admin.register(SmartKPI)
class SmartKPIAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'tenant', 'current_value_display', 
        'performance_status_display', 'data_source_type', 'is_active', 'is_featured'
    )
    list_filter = (
        'category', 'tenant', 'data_source_type', 'calculation_method',
        'trend_direction', 'is_active', 'is_featured', 'auto_update_frequency'
    )
    search_fields = ('name', 'description', 'owner__username')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'last_auto_update', 'next_auto_update',
        'current_value_display', 'performance_status_display'
    )
    raw_id_fields = ('owner',)
    filter_horizontal = ('stakeholders', 'parent_kpis')
    list_editable = ('is_active', 'is_featured')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'category', 'owner', 'stakeholders')
        }),
        ('Data Source & Calculation', {
            'fields': (
                'data_source_type', 'data_source_config', 'calculation_method',
                'calculation_formula', 'parent_kpis'
            )
        }),
        ('Units & Formatting', {
            'fields': ('unit', 'decimal_places', 'chart_type')
        }),
        ('Targets & Thresholds', {
            'fields': (
                'target_value', 'warning_threshold', 'critical_threshold', 'trend_direction'
            )
        }),
        ('Automation', {
            'fields': (
                'auto_update_frequency', 'last_auto_update', 'next_auto_update'
            )
        }),
        ('Status & Display', {
            'fields': ('is_active', 'is_featured', 'current_value_display', 'performance_status_display')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [KPIDataPointInline, KPIAlertInline]
    
    actions = ['activate_kpis', 'deactivate_kpis', 'feature_kpis', 'unfeature_kpis']
    
    def current_value_display(self, obj):
        value = obj.get_latest_value()
        if value is not None:
            if obj.unit == '%':
                return f"{value}%"
            elif obj.unit == '$':
                return f"${value:,.2f}"
            elif obj.unit:
                return f"{value} {obj.unit}"
            else:
                return str(value)
        return format_html('<span style="color: gray;">No data</span>')
    current_value_display.short_description = 'Current Value'
    
    def performance_status_display(self, obj):
        status = obj.calculate_performance_status()
        
        colors = {
            'excellent': 'green',
            'good': 'blue',
            'warning': 'orange',
            'critical': 'red',
            'unknown': 'gray'
        }
        
        icons = {
            'excellent': '✅',
            'good': '👍',
            'warning': '⚠️',
            'critical': '🔴',
            'unknown': '❓'
        }
        
        color = colors.get(status, 'gray')
        icon = icons.get(status, '❓')
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, status.title()
        )
    performance_status_display.short_description = 'Performance'
    
    def activate_kpis(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} KPIs activated.')
    activate_kpis.short_description = 'Activate selected KPIs'
    
    def deactivate_kpis(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} KPIs deactivated.')
    deactivate_kpis.short_description = 'Deactivate selected KPIs'
    
    def feature_kpis(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} KPIs featured on dashboard.')
    feature_kpis.short_description = 'Feature on dashboard'
    
    def unfeature_kpis(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} KPIs removed from featured.')
    unfeature_kpis.short_description = 'Remove from featured'


@admin.register(KPIDataPoint)
class KPIDataPointAdmin(admin.ModelAdmin):
    list_display = (
        'kpi', 'date', 'formatted_value_display', 'source', 
        'entered_by', 'confidence_level', 'is_estimated'
    )
    list_filter = (
        'source', 'is_estimated', 'confidence_level', 'date', 
        'kpi__category', 'kpi__tenant'
    )
    search_fields = ('kpi__name', 'notes', 'entered_by__username')
    readonly_fields = ('id', 'created_at', 'updated_at', 'formatted_value_display')
    raw_id_fields = ('kpi', 'entered_by')
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Data Point', {
            'fields': ('kpi', 'date', 'value', 'formatted_value_display')
        }),
        ('Source & Quality', {
            'fields': ('source', 'entered_by', 'confidence_level', 'is_estimated')
        }),
        ('Additional Information', {
            'fields': ('notes', 'metadata')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def formatted_value_display(self, obj):
        return obj.formatted_value
    formatted_value_display.short_description = 'Formatted Value'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('kpi', 'entered_by')


@admin.register(KPIAlert)
class KPIAlertAdmin(admin.ModelAdmin):
    list_display = (
        'kpi', 'alert_type', 'severity_display', 'title',
        'is_acknowledged', 'is_resolved', 'created_at'
    )
    list_filter = (
        'alert_type', 'severity', 'is_acknowledged', 'is_resolved',
        'created_at', 'kpi__category', 'kpi__tenant'
    )
    search_fields = ('title', 'message', 'kpi__name')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'acknowledged_at', 'resolved_at'
    )
    raw_id_fields = ('kpi', 'acknowledged_by')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('kpi', 'alert_type', 'severity', 'title', 'message')
        }),
        ('Trigger Data', {
            'fields': ('trigger_value', 'threshold_value')
        }),
        ('Status', {
            'fields': (
                'is_acknowledged', 'acknowledged_by', 'acknowledged_at',
                'is_resolved', 'resolved_at'
            )
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['acknowledge_alerts', 'resolve_alerts']
    
    def severity_display(self, obj):
        colors = {
            'info': 'blue',
            'warning': 'orange',
            'critical': 'red'
        }
        
        icons = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'critical': '🚨'
        }
        
        color = colors.get(obj.severity, 'gray')
        icon = icons.get(obj.severity, '❓')
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.get_severity_display()
        )
    severity_display.short_description = 'Severity'
    
    def acknowledge_alerts(self, request, queryset):
        updated = 0
        for alert in queryset.filter(is_acknowledged=False):
            alert.acknowledge(request.user)
            updated += 1
        self.message_user(request, f'{updated} alerts acknowledged.')
    acknowledge_alerts.short_description = 'Acknowledge selected alerts'
    
    def resolve_alerts(self, request, queryset):
        updated = 0
        for alert in queryset.filter(is_resolved=False):
            alert.resolve()
            updated += 1
        self.message_user(request, f'{updated} alerts resolved.')
    resolve_alerts.short_description = 'Resolve selected alerts'


class DashboardKPIInline(admin.TabularInline):
    model = DashboardKPI
    extra = 0
    raw_id_fields = ('kpi',)
    fields = ('kpi', 'position_x', 'position_y', 'width', 'height', 'chart_type_override')


@admin.register(KPIDashboard)
class KPIDashboardAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'owner', 'tenant', 'kpi_count_display', 
        'is_public', 'refresh_interval', 'created_at'
    )
    list_filter = ('tenant', 'is_public', 'created_at')
    search_fields = ('name', 'description', 'owner__username')
    readonly_fields = ('id', 'created_at', 'updated_at', 'kpi_count_display')
    raw_id_fields = ('owner',)
    filter_horizontal = ('shared_with',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'owner')
        }),
        ('Configuration', {
            'fields': ('layout', 'refresh_interval')
        }),
        ('Sharing & Permissions', {
            'fields': ('is_public', 'shared_with')
        }),
        ('Statistics', {
            'fields': ('kpi_count_display',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [DashboardKPIInline]
    
    def kpi_count_display(self, obj):
        count = obj.kpis.count()
        return f"{count} KPIs"
    kpi_count_display.short_description = 'KPI Count'


@admin.register(DashboardKPI)
class DashboardKPIAdmin(admin.ModelAdmin):
    list_display = (
        'dashboard', 'kpi', 'position_display', 'size_display', 'chart_type_override'
    )
    list_filter = ('dashboard__tenant', 'chart_type_override')
    search_fields = ('dashboard__name', 'kpi__name')
    raw_id_fields = ('dashboard', 'kpi')
    
    def position_display(self, obj):
        return f"({obj.position_x}, {obj.position_y})"
    position_display.short_description = 'Position (X, Y)'
    
    def size_display(self, obj):
        return f"{obj.width} × {obj.height}"
    size_display.short_description = 'Size (W × H)'
