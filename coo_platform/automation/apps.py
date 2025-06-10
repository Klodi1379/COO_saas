"""
Automation app configuration.
"""
from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'automation'
    verbose_name = 'Automation'
    
    def ready(self):
        import automation.signals  # Import signals when app is ready
