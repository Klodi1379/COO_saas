#!/usr/bin/env python
"""
Create demo superuser for development.
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
from core.models import UserProfile
from tenants.models import Tenant, TenantUser

def create_demo_user():
    """Create demo superuser and tenant setup."""
    
    # Create superuser if it doesn't exist
    if not User.objects.filter(username='admin').exists():
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123',
            first_name='Admin',
            last_name='User'
        )
        print(f"Created superuser: {user.username}")
        
        # Create profile
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': 'system_admin',
                'subscription_tier': 'enterprise'
            }
        )
        if created:
            print(f"Created profile for: {user.username}")
    else:
        user = User.objects.get(username='admin')
        print(f"Superuser already exists: {user.username}")
    
    # Create demo tenant if it doesn't exist
    if not Tenant.objects.filter(slug='demo-company').exists():
        tenant = Tenant.objects.create(
            name='Demo Company',
            slug='demo-company',
            domain='demo.localhost',
            subscription_tier='professional',
            owner=user
        )
        print(f"Created demo tenant: {tenant.name}")
        
        # Add user to tenant
        membership, created = TenantUser.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={
                'role': 'owner',
                'is_active': True,
                'can_invite_users': True,
                'can_manage_projects': True,
                'can_manage_kpis': True,
                'can_view_analytics': True,
                'can_export_data': True
            }
        )
        if created:
            print(f"Added {user.username} to {tenant.name}")
    else:
        tenant = Tenant.objects.get(slug='demo-company')
        print(f"Demo tenant already exists: {tenant.name}")
    
    print("\nDemo setup complete!")
    print("Login credentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print("  Email: admin@example.com")

if __name__ == '__main__':
    create_demo_user()
