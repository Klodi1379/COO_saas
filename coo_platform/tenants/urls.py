"""
URL configuration for tenants app.
"""
from django.urls import path
from . import views

app_name = 'tenants'

urlpatterns = [
    # Tenant settings and management
    path('settings/', views.TenantSettingsView.as_view(), name='settings'),
    path('switcher/', views.TenantSwitcherView.as_view(), name='switcher'),
    
    # User management
    path('invite/', views.invite_user, name='invite_user'),
    path('accept/<uuid:token>/', views.accept_invitation_view, name='accept_invitation'),
    path('switch/<uuid:tenant_id>/', views.switch_tenant, name='switch_tenant'),
    path('remove-user/<int:user_id>/', views.remove_user, name='remove_user'),
    
    # API endpoints
    path('api/info/', views.tenant_api_info, name='api_info'),
]
