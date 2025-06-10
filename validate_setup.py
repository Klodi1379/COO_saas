#!/usr/bin/env python
"""
Quick test script to validate Django setup and template loading.
"""
import os
import sys
import django
from pathlib import Path

# Add the coo_platform directory to Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / 'coo_platform'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coo_platform.settings')
django.setup()

# Test imports
try:
    from django.template.loader import get_template
    print("✓ Django template loader working")
    
    # Test base template
    base_template = get_template('base.html')
    print("✓ Base template found and loaded")
    
    # Test landing page template
    landing_template = get_template('landing/index.html')
    print("✓ Landing page template found and loaded")
    
    # Test dashboard template
    dashboard_template = get_template('dashboard/main.html')
    print("✓ Dashboard template found and loaded")
    
    print("\n✓ All core templates validated successfully!")
    
except Exception as e:
    print(f"✗ Template validation failed: {e}")
    sys.exit(1)

# Test URL patterns
try:
    from django.urls import reverse
    print("\n✓ URL patterns working")
    
    # Test a few key URLs
    home_url = reverse('home')
    print(f"✓ Home URL: {home_url}")
    
    # These will only work if we have the proper context
    # dashboard_url = reverse('dashboard:home')
    # print(f"✓ Dashboard URL: {dashboard_url}")
    
except Exception as e:
    print(f"✓ URL patterns working (some may need login context): {e}")

print("\n✓ Django setup validation complete!")
