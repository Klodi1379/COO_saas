"""
URL configuration for COO Platform project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Authentication
    path('accounts/', include('allauth.urls')),
    
    # Main application URLs
    path('', TemplateView.as_view(template_name='landing/index.html'), name='home'),
    path('dashboard/', include('dashboard.urls')),
    path('projects/', include('projects.urls')),
    path('kpis/', include('kpis.urls')),
    path('automation/', include('automation.urls')),
    
    # API
    path('api/v1/', include('api.urls')),
    
    # Core functionality
    path('core/', include('core.urls')),
    path('tenants/', include('tenants.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "COO Platform Administration"
admin.site.site_title = "COO Platform Admin"
admin.site.index_title = "Welcome to COO Platform Administration"
