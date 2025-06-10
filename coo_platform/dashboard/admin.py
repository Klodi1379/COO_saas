"""
Admin configuration for dashboard models.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    DashboardWidget, UserDashboard, DashboardWidgetPlacement, DashboardTheme
)


class DashboardWidgetPlacementInline(admin.TabularInline):
    model = DashboardWidgetPlacement
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('widget', 'position_x', 'position_y', 'width', 'height', 'title_override')


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'widget_type', 'tenant', 'created_by', 
        'size', 'is_active', 'is_public', 'created_at'
    )
    list_filter = (
        'widget_type', 'size', 'is_active', 'is_public', 
        'tenant', 'created_at'
    )
    search_fields = ('title', 'description', 'created_by__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields = ('created_by',)
    filter_horizontal = ('shared_with',)
    list_editable = ('is_active', 'is_public')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'title', 'widget_type', 'description', 'created_by')
        }),
        ('Configuration', {
            'fields': ('config', 'size', 'refresh_interval', 'cache_duration')
        }),
        ('Sharing & Status', {
            'fields': ('is_active', 'is_public', 'shared_with')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_widgets', 'deactivate_widgets', 'make_public', 'make_private']
    
    def activate_widgets(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} widgets activated.')
    activate_widgets.short_description = 'Activate selected widgets'
    
    def deactivate_widgets(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} widgets deactivated.')
    deactivate_widgets.short_description = 'Deactivate selected widgets'
    
    def make_public(self, request, queryset):
        updated = queryset.update(is_public=True)
        self.message_user(request, f'{updated} widgets made public.')
    make_public.short_description = 'Make selected widgets public'
    
    def make_private(self, request, queryset):
        updated = queryset.update(is_public=False)
        self.message_user(request, f'{updated} widgets made private.')
    make_private.short_description = 'Make selected widgets private'


@admin.register(UserDashboard)
class UserDashboardAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'user', 'tenant', 'is_default', 
        'widget_count', 'auto_refresh', 'created_at'
    )
    list_filter = (
        'is_default', 'auto_refresh', 'tenant', 'created_at'
    )
    search_fields = ('name', 'user__username', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'widget_count')
    raw_id_fields = ('user',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'user', 'name', 'is_default')
        }),
        ('Layout & Settings', {
            'fields': ('layout_config', 'auto_refresh', 'refresh_interval')
        }),
        ('Statistics', {
            'fields': ('widget_count',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [DashboardWidgetPlacementInline]
    
    def widget_count(self, obj):
        count = obj.widget_placements.count()
        return f"{count} widgets"
    widget_count.short_description = 'Widgets'


@admin.register(DashboardWidgetPlacement)
class DashboardWidgetPlacementAdmin(admin.ModelAdmin):
    list_display = (
        'dashboard', 'widget', 'position_display', 'size_display', 'created_at'
    )
    list_filter = (
        'dashboard__tenant', 'widget__widget_type', 'created_at'
    )
    search_fields = (
        'dashboard__name', 'widget__title', 
        'dashboard__user__username'
    )
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields = ('dashboard', 'widget')
    
    fieldsets = (
        ('Placement Information', {
            'fields': ('dashboard', 'widget')
        }),
        ('Position & Size', {
            'fields': ('position_x', 'position_y', 'width', 'height')
        }),
        ('Overrides', {
            'fields': ('title_override', 'config_override')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def position_display(self, obj):
        return f"({obj.position_x}, {obj.position_y})"
    position_display.short_description = 'Position (X, Y)'
    
    def size_display(self, obj):
        return f"{obj.width} × {obj.height}"
    size_display.short_description = 'Size (W × H)'


@admin.register(DashboardTheme)
class DashboardThemeAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'tenant', 'created_by', 'color_preview', 
        'is_public', 'created_at'
    )
    list_filter = ('tenant', 'is_public', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('id', 'created_at', 'updated_at', 'color_preview')
    raw_id_fields = ('created_by',)
    list_editable = ('is_public',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'description', 'created_by', 'is_public')
        }),
        ('Color Scheme', {
            'fields': (
                'primary_color', 'secondary_color', 
                'background_color', 'text_color', 'color_preview'
            )
        }),
        ('Configuration', {
            'fields': ('theme_config',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def color_preview(self, obj):
        return format_html(
            '<div style="display: flex; gap: 5px;">'
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc;" title="Primary"></div>'
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc;" title="Secondary"></div>'
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc;" title="Background"></div>'
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc;" title="Text"></div>'
            '</div>',
            obj.primary_color, obj.secondary_color, 
            obj.background_color, obj.text_color
        )
    color_preview.short_description = 'Color Preview'
