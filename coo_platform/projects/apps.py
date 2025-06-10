"""
Projects app configuration.
"""
from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projects'
    verbose_name = 'Projects'
    
    def ready(self):
        import projects.signals  # Import signals when app is ready
