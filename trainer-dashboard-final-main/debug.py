import os
import sys

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trainer_monitoring.settings')

import django
django.setup()

from django.template.loader import get_template
from django.contrib.staticfiles import finders

print("=== DEBUG STATIC FILES ===")

# Check CSS file
css_path = finders.find('core/admin.css')
print(f"CSS Path: {css_path}")
print(f"CSS Exists: {os.path.exists(css_path) if css_path else 'NOT FOUND'}")

# Check template
try:
    template = get_template('admin/base.html')
    print("✓ Template found: admin/base.html")
except:
    print("✗ Template NOT found: admin/base.html")

print("=== DEBUG COMPLETE ===")