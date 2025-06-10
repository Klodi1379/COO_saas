"""
URL configuration for API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet)
router.register(r'project-categories', views.ProjectCategoryViewSet)
router.register(r'tasks', views.TaskViewSet)
router.register(r'kpis', views.SmartKPIViewSet)
router.register(r'kpi-categories', views.KPICategoryViewSet)
router.register(r'kpi-alerts', views.KPIAlertViewSet)
router.register(r'automation-rules', views.AutomationRuleViewSet)
router.register(r'notifications', views.NotificationViewSet)

app_name = 'api'

urlpatterns = [
    # Authentication
    path('auth/token/', obtain_auth_token, name='api_token_auth'),
    
    # Dashboard and analytics endpoints
    path('dashboard/summary/', views.dashboard_summary, name='dashboard_summary'),
    path('analytics/platform/', views.platform_analytics, name='platform_analytics'),
    
    # Include router URLs
    path('', include(router.urls)),
    
    # API authentication endpoints from DRF
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
]
