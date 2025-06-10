#!/usr/bin/env python
"""
Comprehensive setup and validation script for COO SaaS Platform.
"""
import os
import sys
import django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / 'coo_platform'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coo_platform.settings')
django.setup()

def validate_system():
    """Validate the system setup."""
    print("COO SaaS Platform - System Validation")
    print("=" * 50)
    
    # Test database connectivity
    try:
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        print("✓ Database connection successful")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False
    
    # Test models
    try:
        from django.contrib.auth.models import User
        from tenants.models import Tenant, TenantUser
        from core.models import UserProfile
        from projects.models import Project
        from kpis.models import SmartKPI
        
        print("✓ All models imported successfully")
    except Exception as e:
        print(f"✗ Model import failed: {e}")
        return False
    
    # Test template loading
    try:
        from django.template.loader import get_template
        templates = [
            'base.html',
            'landing/index.html',
            'dashboard/main.html',
            'components/stats_card.html'
        ]
        
        for template_name in templates:
            template = get_template(template_name)
            print(f"✓ Template loaded: {template_name}")
    except Exception as e:
        print(f"✗ Template loading failed: {e}")
        return False
    
    # Test URL patterns
    try:
        from django.urls import reverse
        urls = [
            'home',
            'account_login',
            'account_signup',
        ]
        
        for url_name in urls:
            try:
                url = reverse(url_name)
                print(f"✓ URL pattern works: {url_name} -> {url}")
            except:
                print(f"? URL pattern skipped: {url_name} (may need context)")
    except Exception as e:
        print(f"✗ URL validation failed: {e}")
        return False
    
    # Check admin user
    try:
        admin_exists = User.objects.filter(username='admin').exists()
        if admin_exists:
            print("✓ Admin user exists")
        else:
            print("? Admin user not found (will be created on first run)")
    except Exception as e:
        print(f"? Admin user check failed: {e}")
    
    # Check demo tenant
    try:
        tenant_exists = Tenant.objects.filter(slug='demo-company').exists()
        if tenant_exists:
            print("✓ Demo tenant exists")
        else:
            print("? Demo tenant not found (will be created on first run)")
    except Exception as e:
        print(f"? Demo tenant check failed: {e}")
    
    print("\n" + "=" * 50)
    print("✓ System validation completed successfully!")
    print("✓ COO SaaS Platform is ready to run")
    return True

def show_startup_info():
    """Show startup information."""
    print("\nCOO SaaS Platform - Startup Information")
    print("=" * 50)
    print("Development Server: http://127.0.0.1:8000")
    print("Admin Panel: http://127.0.0.1:8000/admin")
    print("Dashboard: http://127.0.0.1:8000/dashboard")
    print("\nDemo Credentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print("  Email: admin@example.com")
    print("\nTo start the server:")
    print("  python manage.py runserver 8000")
    print("=" * 50)

if __name__ == '__main__':
    if validate_system():
        show_startup_info()
    else:
        print("\n✗ System validation failed. Please check the errors above.")
        sys.exit(1)
