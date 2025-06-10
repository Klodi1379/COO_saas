"""
URL configuration for KPIs app.
"""
from django.urls import path
from . import views

app_name = 'kpis'

urlpatterns = [
    # KPI URLs
    path('', views.KPIListView.as_view(), name='list'),
    path('create/', views.KPICreateView.as_view(), name='create'),
    path('<uuid:pk>/', views.KPIDetailView.as_view(), name='detail'),
    
    # KPI data management
    path('<uuid:kpi_id>/add-data/', views.add_kpi_datapoint, name='add_datapoint'),
    
    # Dashboard URLs
    path('dashboard/', views.kpi_dashboard_view, name='dashboard'),
    path('dashboard/<uuid:dashboard_id>/', views.kpi_dashboard_view, name='dashboard_view'),
    
    # Category management
    path('categories/create/', views.KPICategoryCreateView.as_view(), name='create_category'),
    
    # Alert management
    path('alerts/<uuid:alert_id>/acknowledge/', views.acknowledge_alert, name='acknowledge_alert'),
    
    # API endpoints
    path('<uuid:kpi_id>/api/chart-data/', views.kpi_chart_data, name='chart_data'),
    path('api/analytics/', views.kpi_analytics_data, name='analytics_data'),
]
