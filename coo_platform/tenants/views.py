"""
Views for tenant management.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from .models import Tenant, TenantUser, TenantInvitation
from .utils import (
    invite_user_to_tenant, accept_invitation, 
    get_user_tenants, switch_user_tenant
)
from core.utils import log_user_action


class TenantSettingsView(LoginRequiredMixin, TemplateView):
    """
    Tenant settings and management view.
    """
    template_name = 'tenants/settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            messages.error(self.request, 'No tenant found.')
            return context
        
        # Get current user's tenant relationship
        tenant_user = TenantUser.objects.filter(
            user=self.request.user,
            tenant=tenant
        ).first()
        
        context.update({
            'tenant': tenant,
            'tenant_user': tenant_user,
            'can_manage': tenant_user and tenant_user.role in ['owner', 'admin'],
            'tenant_users': TenantUser.objects.filter(tenant=tenant).select_related('user'),
            'pending_invitations': TenantInvitation.objects.filter(
                tenant=tenant,
                is_accepted=False
            ).filter(expires_at__gt=timezone.now()),
        })
        
        return context


@login_required
def invite_user(request):
    """
    Invite a user to join the current tenant.
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        messages.error(request, 'No tenant found.')
        return redirect('dashboard:home')
    
    # Check permissions
    tenant_user = TenantUser.objects.filter(
        user=request.user,
        tenant=tenant
    ).first()
    
    if not tenant_user or not tenant_user.can_invite_users:
        messages.error(request, 'You do not have permission to invite users.')
        return redirect('tenants:settings')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        role = request.POST.get('role', 'user')
        
        if not email:
            messages.error(request, 'Email is required.')
            return redirect('tenants:settings')
        
        try:
            invitation = invite_user_to_tenant(
                tenant=tenant,
                email=email,
                role=role,
                invited_by=request.user,
                send_email=True
            )
            
            log_user_action(
                request, 'create', 'TenantInvitation', 
                str(invitation.id), f'Invited {email} as {role}'
            )
            
            messages.success(request, f'Invitation sent to {email}.')
            
        except ValueError as e:
            messages.error(request, str(e))
    
    return redirect('tenants:settings')


def accept_invitation_view(request, token):
    """
    Accept a tenant invitation.
    """
    invitation = get_object_or_404(TenantInvitation, token=token)
    
    if invitation.is_accepted:
        messages.info(request, 'This invitation has already been accepted.')
        return redirect('dashboard:home')
    
    if invitation.is_expired:
        messages.error(request, 'This invitation has expired.')
        return redirect('home')
    
    if not request.user.is_authenticated:
        # Store invitation token in session and redirect to login
        request.session['invitation_token'] = str(token)
        messages.info(request, 'Please log in or create an account to accept this invitation.')
        return redirect('account_login')
    
    # Check if user email matches invitation email
    if request.user.email != invitation.email:
        messages.error(request, 'This invitation is for a different email address.')
        return redirect('home')
    
    try:
        tenant_user = accept_invitation(invitation, request.user)
        
        log_user_action(
            request, 'create', 'TenantUser', 
            str(tenant_user.id), f'Accepted invitation to {invitation.tenant.name}'
        )
        
        messages.success(request, f'Welcome to {invitation.tenant.name}!')
        
        # Switch to this tenant
        switch_user_tenant(request.user, invitation.tenant)
        
        return redirect('dashboard:home')
        
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('home')


@login_required
def switch_tenant(request, tenant_id):
    """
    Switch user's active tenant.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if switch_user_tenant(request.user, tenant):
        messages.success(request, f'Switched to {tenant.name}.')
    else:
        messages.error(request, 'You do not have access to this organization.')
    
    return redirect('dashboard:home')


@login_required
def remove_user(request, user_id):
    """
    Remove a user from the current tenant.
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        messages.error(request, 'No tenant found.')
        return redirect('dashboard:home')
    
    # Check permissions
    requester_tenant_user = TenantUser.objects.filter(
        user=request.user,
        tenant=tenant
    ).first()
    
    if not requester_tenant_user or requester_tenant_user.role not in ['owner', 'admin']:
        messages.error(request, 'You do not have permission to remove users.')
        return redirect('tenants:settings')
    
    # Get the user to remove
    user_to_remove = get_object_or_404(User, id=user_id)
    tenant_user_to_remove = get_object_or_404(
        TenantUser, 
        user=user_to_remove, 
        tenant=tenant
    )
    
    # Prevent removing the last owner
    if tenant_user_to_remove.role == 'owner':
        owner_count = TenantUser.objects.filter(
            tenant=tenant, 
            role='owner', 
            is_active=True
        ).count()
        
        if owner_count <= 1:
            messages.error(request, 'Cannot remove the last owner.')
            return redirect('tenants:settings')
    
    # Remove the user
    tenant_user_to_remove.delete()
    
    log_user_action(
        request, 'delete', 'TenantUser', 
        str(tenant_user_to_remove.id), 
        f'Removed {user_to_remove.username} from {tenant.name}'
    )
    
    messages.success(request, f'{user_to_remove.get_full_name() or user_to_remove.username} has been removed.')
    
    return redirect('tenants:settings')


class TenantSwitcherView(LoginRequiredMixin, TemplateView):
    """
    View for switching between tenants.
    """
    template_name = 'tenants/switcher.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user_tenants = get_user_tenants(self.request.user)
        current_tenant = getattr(self.request, 'tenant', None)
        
        context.update({
            'user_tenants': user_tenants,
            'current_tenant': current_tenant,
        })
        
        return context


@login_required
def tenant_api_info(request):
    """
    API endpoint for tenant information (for AJAX calls).
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'No tenant found'}, status=404)
    
    tenant_user = TenantUser.objects.filter(
        user=request.user,
        tenant=tenant
    ).first()
    
    data = {
        'tenant': {
            'id': str(tenant.id),
            'name': tenant.name,
            'slug': tenant.slug,
            'subscription_tier': tenant.subscription_tier,
            'status': tenant.status,
            'user_count': tenant.user_count,
            'max_users': tenant.max_users,
            'project_count': tenant.project_count,
            'max_projects': tenant.max_projects,
        },
        'user_role': tenant_user.role if tenant_user else None,
        'permissions': {
            'can_invite_users': tenant_user.can_invite_users if tenant_user else False,
            'can_manage_projects': tenant_user.can_manage_projects if tenant_user else False,
            'can_manage_kpis': tenant_user.can_manage_kpis if tenant_user else False,
            'can_view_analytics': tenant_user.can_view_analytics if tenant_user else False,
            'can_export_data': tenant_user.can_export_data if tenant_user else False,
        }
    }
    
    return JsonResponse(data)
