"""
KPIs app configuration.
"""
from django.apps import AppConfig


class KpisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kpis'
    verbose_name = 'KPIs'
    
    def ready(self):
        import kpis.signals  # Import signals when app is ready
