"""
URL configuration for dashboard app.
"""
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Main dashboard
    path('', views.MainDashboardView.as_view(), name='home'),
    path('settings/', views.DashboardSettingsView.as_view(), name='settings'),
    
    # Widget management
    path('widgets/<uuid:widget_id>/data/', views.widget_data_api, name='widget_data'),
    path('widgets/add/', views.add_widget_to_dashboard, name='add_widget'),
    path('widgets/remove/<uuid:placement_id>/', views.remove_widget_from_dashboard, name='remove_widget'),
    
    # Dashboard management
    path('layout/update/', views.update_dashboard_layout, name='update_layout'),
    path('export/', views.dashboard_export, name='export'),
    
    # Real-time updates
    path('api/updates/', views.real_time_updates, name='real_time_updates'),
]
