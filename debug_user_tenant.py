#!/usr/bin/env python
"""
Debug script to check user and tenant relationships.
"""
import os
import sys
import django
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / 'coo_platform'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coo_platform.settings')
django.setup()

from django.contrib.auth.models import User
from tenants.models import Tenant, TenantUser

def debug_user_tenant_relationship():
    """Debug user-tenant relationships."""
    print("=== USER-TENANT RELATIONSHIP DEBUG ===")
    
    # Check if admin user exists
    try:
        admin_user = User.objects.get(username='admin')
        print(f"Admin user found: {admin_user.username} (ID: {admin_user.id})")
        print(f"Email: {admin_user.email}")
        print(f"Is active: {admin_user.is_active}")
    except User.DoesNotExist:
        print("Admin user not found!")
        return
    
    # Check tenant memberships
    memberships = TenantUser.objects.filter(user=admin_user)
    print(f"\nTenant memberships for {admin_user.username}: {memberships.count()}")
    
    for membership in memberships:
        print(f"  - Tenant: {membership.tenant.name} (ID: {membership.tenant.id})")
        print(f"    Role: {membership.role}")
        print(f"    Active: {membership.is_active}")
        print(f"    Can manage projects: {membership.can_manage_projects}")
    
    # Check all tenants
    tenants = Tenant.objects.all()
    print(f"\nAll tenants in system: {tenants.count()}")
    for tenant in tenants:
        print(f"  - {tenant.name} (Slug: {tenant.slug})")
        print(f"    Owner: {tenant.owner}")
        print(f"    Status: {tenant.status}")
    
    # Test the specific query used in the view
    print("\n=== TESTING VIEW LOGIC ===")
    tenant_user = admin_user.tenant_memberships.filter(is_active=True).first()
    if tenant_user:
        print(f"Found active tenant membership: {tenant_user.tenant.name}")
        print(f"User can create projects: {tenant_user.can_manage_projects}")
    else:
        print("No active tenant membership found!")
        print("This is likely the issue causing the form to fail silently.")
    
    # Check related_name on TenantUser model
    print(f"\nDirect query - TenantUser for admin: {TenantUser.objects.filter(user=admin_user).count()}")

if __name__ == '__main__':
    debug_user_tenant_relationship()
