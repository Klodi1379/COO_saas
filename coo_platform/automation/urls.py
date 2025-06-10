"""
URL configuration for automation app.
"""
from django.urls import path
from . import views

app_name = 'automation'

urlpatterns = [
    # Automation rule URLs
    path('', views.AutomationRuleListView.as_view(), name='list'),
    path('create/', views.AutomationRuleCreateView.as_view(), name='create'),
    path('<uuid:pk>/', views.AutomationRuleDetailView.as_view(), name='detail'),
    
    # Rule management
    path('<uuid:rule_id>/toggle/', views.toggle_rule_status, name='toggle_status'),
    path('<uuid:rule_id>/execute/', views.execute_rule_manually, name='execute'),
    
    # Action management
    path('<uuid:rule_id>/actions/create/', views.create_automation_action, name='create_action'),
    
    # API endpoints
    path('api/analytics/', views.automation_analytics, name='analytics'),
]
