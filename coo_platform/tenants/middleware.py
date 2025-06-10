"""
Middleware for handling multi-tenant functionality.
"""
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.db import models
from .models import Tenant, TenantUser
from .utils import get_tenant_from_request
import threading


# Thread-local storage for current tenant
_tenant_context = threading.local()


class TenantMiddleware:
    """
    Middleware to resolve and set the current tenant for each request.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip tenant resolution for certain paths
        skip_paths = [
            '/admin/',
            '/accounts/',
            '/api/public/',
            '/static/',
            '/media/',
        ]
        
        if any(request.path.startswith(path) for path in skip_paths):
            request.tenant = None
            return self.get_response(request)
        
        # Try to resolve tenant
        tenant = self.resolve_tenant(request)
        
        if tenant:
            # Check if tenant is active
            if not tenant.is_active and tenant.status != 'trial':
                messages.error(request, "This account has been suspended. Please contact support.")
                return redirect('home')
            
            # Check if user has access to this tenant
            if request.user.is_authenticated:
                if not self.user_has_tenant_access(request.user, tenant):
                    messages.error(request, "You don't have access to this organization.")
                    return redirect('home')
        
        # Set tenant in request and thread-local storage
        request.tenant = tenant
        set_current_tenant(tenant)
        
        response = self.get_response(request)
        
        # Clear tenant from thread-local storage
        clear_current_tenant()
        
        return response
    
    def resolve_tenant(self, request):
        """
        Resolve tenant from the request.
        Priority: subdomain > domain > user's default tenant
        """
        tenant = None
        
        # Try to get tenant from subdomain (e.g., client1.cooplatform.com)
        host = request.get_host().lower()
        host_parts = host.split('.')
        
        if len(host_parts) > 2:  # Has subdomain
            subdomain = host_parts[0]
            if subdomain != 'www':
                try:
                    tenant = Tenant.objects.get(slug=subdomain)
                except Tenant.DoesNotExist:
                    pass
        
        # Try to get tenant from custom domain
        if not tenant:
            try:
                tenant = Tenant.objects.get(domain=host)
            except Tenant.DoesNotExist:
                pass
        
        # For authenticated users, try to get their default/primary tenant
        if not tenant and request.user.is_authenticated:
            tenant_user = TenantUser.objects.filter(
                user=request.user,
                is_active=True
            ).first()
            
            if tenant_user:
                tenant = tenant_user.tenant
        
        return tenant
    
    def user_has_tenant_access(self, user, tenant):
        """
        Check if user has access to the specified tenant.
        """
        if user.is_superuser:
            return True
        
        # Check if user is a consultant (can access all tenants)
        if hasattr(user, 'profile') and user.profile.is_consultant:
            return True
        
        # Check if user is a member of this tenant
        return TenantUser.objects.filter(
            user=user,
            tenant=tenant,
            is_active=True
        ).exists()


class TenantQuerysetMiddleware:
    """
    Middleware to automatically filter querysets by current tenant.
    This ensures data isolation at the database level.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response


def get_current_tenant():
    """
    Get the current tenant from thread-local storage.
    """
    return getattr(_tenant_context, 'tenant', None)


def set_current_tenant(tenant):
    """
    Set the current tenant in thread-local storage.
    """
    _tenant_context.tenant = tenant


def clear_current_tenant():
    """
    Clear the current tenant from thread-local storage.
    """
    if hasattr(_tenant_context, 'tenant'):
        delattr(_tenant_context, 'tenant')


class TenantAwareManager(models.Manager):
    """
    Manager that automatically filters by current tenant.
    """
    
    def get_queryset(self):
        from django.db import models
        
        tenant = get_current_tenant()
        if tenant:
            return super().get_queryset().filter(tenant=tenant)
        return super().get_queryset()


def tenant_context(tenant):
    """
    Context manager for temporarily setting a tenant.
    
    Usage:
        with tenant_context(tenant):
            # All database queries will be filtered by this tenant
            projects = Project.objects.all()
    """
    class TenantContext:
        def __init__(self, tenant):
            self.tenant = tenant
            self.previous_tenant = None
        
        def __enter__(self):
            self.previous_tenant = get_current_tenant()
            set_current_tenant(self.tenant)
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            set_current_tenant(self.previous_tenant)
    
    return TenantContext(tenant)
