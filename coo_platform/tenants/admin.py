"""
Admin configuration for tenant models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Tenant, TenantUser, TenantInvitation, ActiveTenant, TrialTenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'slug', 'subscription_tier', 'status', 
        'user_count_display', 'trial_ends_at', 'created_at'
    )
    list_filter = ('subscription_tier', 'status', 'created_at', 'trial_ends_at')
    search_fields = ('name', 'slug', 'contact_email', 'domain')
    readonly_fields = ('id', 'created_at', 'updated_at', 'user_count_display')
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'domain', 'contact_email', 'contact_phone', 'address')
        }),
        ('Subscription & Status', {
            'fields': (
                'subscription_tier', 'status', 'trial_ends_at', 
                'subscription_starts_at', 'subscription_ends_at'
            )
        }),
        ('Billing', {
            'fields': ('billing_email', 'stripe_customer_id', 'stripe_subscription_id'),
            'classes': ('collapse',)
        }),
        ('Limits & Configuration', {
            'fields': ('max_users', 'max_projects', 'max_storage_mb', 'settings', 'features')
        }),
        ('Branding', {
            'fields': ('logo', 'primary_color', 'secondary_color'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'user_count_display', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_tenants', 'suspend_tenants', 'extend_trial']
    
    def user_count_display(self, obj):
        count = obj.user_count
        url = reverse('admin:tenants_tenantuser_changelist') + f'?tenant__id={obj.id}'
        return format_html('<a href="{}">{} users</a>', url, count)
    user_count_display.short_description = 'Users'
    
    def activate_tenants(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} tenants activated.')
    activate_tenants.short_description = 'Activate selected tenants'
    
    def suspend_tenants(self, request, queryset):
        updated = queryset.update(status='suspended')
        self.message_user(request, f'{updated} tenants suspended.')
    suspend_tenants.short_description = 'Suspend selected tenants'
    
    def extend_trial(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        
        updated = 0
        for tenant in queryset.filter(status='trial'):
            tenant.trial_ends_at = timezone.now() + timedelta(days=14)
            tenant.save()
            updated += 1
        
        self.message_user(request, f'{updated} trial periods extended by 14 days.')
    extend_trial.short_description = 'Extend trial by 14 days'


@admin.register(ActiveTenant)
class ActiveTenantAdmin(TenantAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(status='active')


@admin.register(TrialTenant)
class TrialTenantAdmin(TenantAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(status='trial')
    
    list_display = TenantAdmin.list_display + ('trial_days_remaining',)
    
    def trial_days_remaining(self, obj):
        from django.utils import timezone
        
        if not obj.trial_ends_at:
            return 'No trial end date'
        
        remaining = obj.trial_ends_at - timezone.now()
        if remaining.days < 0:
            return format_html('<span style="color: red;">Expired</span>')
        elif remaining.days <= 3:
            return format_html('<span style="color: orange;">{} days</span>', remaining.days)
        else:
            return f'{remaining.days} days'
    trial_days_remaining.short_description = 'Trial Remaining'


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'tenant', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at', 'tenant__subscription_tier')
    search_fields = (
        'user__username', 'user__email', 'user__first_name', 'user__last_name',
        'tenant__name'
    )
    raw_id_fields = ('user', 'tenant')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'user', 'role', 'is_active')
        }),
        ('Permissions', {
            'fields': (
                'can_invite_users', 'can_manage_projects', 'can_manage_kpis',
                'can_view_analytics', 'can_export_data'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'tenant')


@admin.register(TenantInvitation)
class TenantInvitationAdmin(admin.ModelAdmin):
    list_display = (
        'email', 'tenant', 'role', 'invited_by', 
        'is_accepted', 'is_expired_display', 'created_at'
    )
    list_filter = ('role', 'is_accepted', 'created_at', 'expires_at')
    search_fields = ('email', 'tenant__name', 'invited_by__username')
    readonly_fields = (
        'id', 'token', 'created_at', 'updated_at', 
        'accepted_at', 'is_expired_display'
    )
    raw_id_fields = ('tenant', 'invited_by')
    
    fieldsets = (
        ('Invitation Details', {
            'fields': ('tenant', 'email', 'role', 'invited_by')
        }),
        ('Status', {
            'fields': ('is_accepted', 'accepted_at', 'expires_at', 'is_expired_display')
        }),
        ('Security', {
            'fields': ('id', 'token'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['resend_invitations', 'extend_expiry']
    
    def is_expired_display(self, obj):
        if obj.is_expired:
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Valid</span>')
    is_expired_display.short_description = 'Status'
    
    def resend_invitations(self, request, queryset):
        from .utils import send_invitation_email
        
        sent = 0
        for invitation in queryset.filter(is_accepted=False):
            if not invitation.is_expired:
                send_invitation_email(invitation)
                sent += 1
        
        self.message_user(request, f'{sent} invitations resent.')
    resend_invitations.short_description = 'Resend selected invitations'
    
    def extend_expiry(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        
        updated = queryset.filter(is_accepted=False).update(
            expires_at=timezone.now() + timedelta(days=7)
        )
        self.message_user(request, f'{updated} invitation expiry dates extended.')
    extend_expiry.short_description = 'Extend expiry by 7 days'
