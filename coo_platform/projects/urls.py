"""
URL configuration for projects app.
"""
from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    # Project URLs
    path('', views.ProjectListView.as_view(), name='list'),
    path('create/', views.ProjectCreateView.as_view(), name='create'),
    path('<uuid:pk>/', views.ProjectDetailView.as_view(), name='detail'),
    path('<uuid:pk>/edit/', views.ProjectUpdateView.as_view(), name='update'),
    
    # Task management URLs
    path('<uuid:project_id>/tasks/create/', views.create_task, name='create_task'),
    path('tasks/<uuid:task_id>/status/', views.update_task_status, name='update_task_status'),
    
    # API endpoints
    path('<uuid:project_id>/api/dashboard/', views.project_dashboard_data, name='dashboard_data'),
]
