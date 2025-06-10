"""
URL configuration for core app.
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Notifications
    path('notifications/', views.notifications_list, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/api/', views.notifications_api, name='notifications_api'),
    
    # User profile and settings
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('activity/', views.user_activity_log, name='activity_log'),
    
    # Search
    path('search/', views.search_global, name='search'),
]
