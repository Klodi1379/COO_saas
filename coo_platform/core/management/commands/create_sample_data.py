"""
Management command to create sample data for development and demo purposes.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from core.models import UserProfile, Notification
from tenants.models import Tenant
from projects.models import Project, ProjectCategory, Task
from kpis.models import KPICategory, SmartKPI
from dashboard.models import DashboardWidget, UserDashboard, DashboardWidgetPlacement
from datetime import datetime, timedelta
import random


class Command(BaseCommand):
    help = 'Create sample data for development and demo'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@demo.com',
            help='Email for the admin user',
        )
        parser.add_argument(
            '--tenant-name',
            type=str,
            default='Demo Company',
            help='Name for the demo tenant',
        )
    
    def handle(self, *args, **options):
        admin_email = options['admin_email']
        tenant_name = options['tenant_name']
        
        self.stdout.write('Creating sample data...')
        
        with transaction.atomic():
            # Create tenant
            tenant, created = Tenant.objects.get_or_create(
                name=tenant_name,
                defaults={
                    'slug': 'demo-company',
                    'subscription_tier': 'professional',
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(f'Created tenant: {tenant.name}')
            
            # Create admin user
            admin_user, created = User.objects.get_or_create(
                email=admin_email,
                defaults={
                    'username': 'admin',
                    'first_name': 'Admin',
                    'last_name': 'User',
                    'is_staff': True,
                    'is_superuser': True
                }
            )
            
            if created:
                admin_user.set_password('admin123')
                admin_user.save()
                self.stdout.write(f'Created admin user: {admin_user.email}')
            
            # Create user profile
            profile, created = UserProfile.objects.get_or_create(
                user=admin_user,
                defaults={
                    'role': 'client_admin',
                    'subscription_tier': 'professional',
                    'email_notifications': True
                }
            )
            
            # Create additional users
            users = []
            for i, (first, last, role) in enumerate([
                ('John', 'Smith', 'client_user'),
                ('Sarah', 'Johnson', 'client_user'), 
                ('Mike', 'Williams', 'client_user'),
                ('Lisa', 'Brown', 'client_admin')
            ]):
                user, created = User.objects.get_or_create(
                    email=f'{first.lower()}.{last.lower()}@demo.com',
                    defaults={
                        'username': f'{first.lower()}.{last.lower()}',
                        'first_name': first,
                        'last_name': last
                    }
                )
                if created:
                    user.set_password('demo123')
                    user.save()
                    
                    # Create profile
                    UserProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'role': role,
                            'subscription_tier': 'professional'
                        }
                    )
                    
                users.append(user)
            
            self.stdout.write(f'Created {len(users)} additional users')
            
            # Create project categories
            categories_data = [
                ('Product Development', 'Development of new products and features', '#007bff'),
                ('Marketing Campaigns', 'Marketing and promotional activities', '#28a745'),
                ('Operations', 'Operational improvements and processes', '#ffc107'),
                ('Customer Success', 'Customer support and success initiatives', '#17a2b8'),
            ]
            
            categories = []
            for name, description, color in categories_data:
                category, created = ProjectCategory.objects.get_or_create(
                    tenant=tenant,
                    name=name,
                    defaults={
                        'description': description,
                        'color': color
                    }
                )
                categories.append(category)
            
            self.stdout.write(f'Created {len(categories)} project categories')
            
            # Create projects
            projects_data = [
                ('Mobile App Redesign', 'Complete redesign of mobile application', 'active', 'high', categories[0]),
                ('Q1 Marketing Campaign', 'Launch marketing campaign for Q1', 'active', 'medium', categories[1]),
                ('Process Automation', 'Automate manual processes', 'planning', 'medium', categories[2]),
                ('Customer Onboarding', 'Improve customer onboarding flow', 'active', 'high', categories[3]),
                ('Website Performance', 'Optimize website performance', 'completed', 'low', categories[0]),
            ]
            
            projects = []
            for name, description, status, priority, category in projects_data:
                project, created = Project.objects.get_or_create(
                    tenant=tenant,
                    name=name,
                    defaults={
                        'description': description,
                        'status': status,
                        'priority': priority,
                        'category': category,
                        'project_manager': random.choice(users + [admin_user]),
                        'start_date': timezone.now().date() - timedelta(days=random.randint(10, 60)),
                        'target_end_date': timezone.now().date() + timedelta(days=random.randint(30, 120)),
                        'progress_percentage': random.randint(10, 90) if status != 'completed' else 100,
                        'budget_allocated': random.randint(10000, 100000)
                    }
                )
                projects.append(project)
            
            self.stdout.write(f'Created {len(projects)} projects')
            
            # Create tasks
            task_count = 0
            for project in projects:
                num_tasks = random.randint(3, 8)
                for i in range(num_tasks):
                    task, created = Task.objects.get_or_create(
                        project=project,
                        title=f'Task {i+1} for {project.name}',
                        defaults={
                            'description': f'Sample task description for {project.name}',
                            'assigned_to': random.choice(users + [admin_user]),
                            'created_by': admin_user,
                            'status': random.choice(['todo', 'in_progress', 'completed', 'review']),
                            'priority': random.choice(['low', 'medium', 'high']),
                            'due_date': timezone.now() + timedelta(days=random.randint(1, 30)),
                            'estimated_hours': random.randint(2, 16)
                        }
                    )
                    if created:
                        task_count += 1
            
            self.stdout.write(f'Created {task_count} tasks')
            
            # Create KPI categories
            kpi_categories_data = [
                ('Financial', 'financial', 'Financial performance metrics', '#28a745'),
                ('Operational', 'operational', 'Operational efficiency metrics', '#007bff'),
                ('Customer', 'customer', 'Customer satisfaction metrics', '#17a2b8'),
                ('Growth', 'growth', 'Business growth metrics', '#ffc107'),
            ]
            
            kpi_categories = []
            for name, cat_type, description, color in kpi_categories_data:
                category, created = KPICategory.objects.get_or_create(
                    tenant=tenant,
                    name=name,
                    defaults={
                        'category_type': cat_type,
                        'description': description,
                        'color': color
                    }
                )
                kpi_categories.append(category)
            
            self.stdout.write(f'Created {len(kpi_categories)} KPI categories')
            
            # Create KPIs
            kpis_data = [
                ('Monthly Revenue', 'monthly', '$', 50000, 45000, 40000, kpi_categories[0]),
                ('Customer Satisfaction', 'weekly', '%', 95, 85, 75, kpi_categories[2]),
                ('Process Efficiency', 'daily', '%', 90, 80, 70, kpi_categories[1]),
                ('New Customers', 'monthly', 'count', 100, 80, 60, kpi_categories[3]),
                ('Support Response Time', 'daily', 'hours', 2, 4, 8, kpi_categories[2]),
            ]
            
            kpis = []
            for name, frequency, unit, target, warning, critical, category in kpis_data:
                kpi, created = SmartKPI.objects.get_or_create(
                    tenant=tenant,
                    name=name,
                    defaults={
                        'category': category,
                        'auto_update_frequency': frequency,
                        'unit': unit,
                        'target_value': target,
                        'warning_threshold': warning,
                        'critical_threshold': critical,
                        'owner': admin_user,
                        'is_featured': True,
                        'trend_direction': 'down_good' if 'time' in name.lower() else 'up_good'
                    }
                )
                kpis.append(kpi)
            
            self.stdout.write(f'Created {len(kpis)} KPIs')
            
            # Create sample notifications
            notifications_data = [
                ('Task Assignment', 'You have been assigned a new task: "Update documentation"', 'task_assigned'),
                ('KPI Alert', 'Customer Satisfaction has dropped below warning threshold', 'kpi_alert'),
                ('Project Update', 'Mobile App Redesign project has been updated', 'info'),
                ('Deadline Approaching', 'Task "Review designs" is due tomorrow', 'deadline_approaching'),
                ('System Update', 'System maintenance scheduled for tonight', 'system'),
            ]
            
            notification_count = 0
            for title, message, notif_type in notifications_data:
                for user in [admin_user] + users[:2]:  # Send to admin and first 2 users
                    notification, created = Notification.objects.get_or_create(
                        recipient=user,
                        title=title,
                        defaults={
                            'message': message,
                            'notification_type': notif_type,
                            'is_read': random.choice([True, False])
                        }
                    )
                    if created:
                        notification_count += 1
            
            self.stdout.write(f'Created {notification_count} notifications')
            
            # Create dashboard widgets
            widgets_data = [
                ('Project Overview', 'project_overview', 'Overview of all projects'),
                ('My Tasks', 'task_list', 'Tasks assigned to me'),
                ('KPI Summary', 'kpi_summary', 'Summary of key KPIs'),
                ('Recent Activity', 'recent_activity', 'Recent platform activity'),
                ('Critical Alerts', 'alerts_summary', 'Critical alerts and warnings'),
            ]
            
            widgets = []
            for title, widget_type, description in widgets_data:
                widget, created = DashboardWidget.objects.get_or_create(
                    tenant=tenant,
                    title=title,
                    widget_type=widget_type,
                    defaults={
                        'description': description,
                        'created_by': admin_user,
                        'is_public': True,
                        'config': {
                            'limit': 10 if 'list' in widget_type else 5
                        }
                    }
                )
                widgets.append(widget)
            
            self.stdout.write(f'Created {len(widgets)} dashboard widgets')
            
            # Create user dashboards with widget placements
            for user in [admin_user] + users:
                dashboard, created = UserDashboard.objects.get_or_create(
                    user=user,
                    tenant=tenant,
                    is_default=True,
                    defaults={
                        'name': 'My Dashboard'
                    }
                )
                
                if created:
                    # Add widgets to dashboard
                    positions = [
                        (0, 0, 6, 3),  # Project Overview
                        (6, 0, 6, 3),  # My Tasks  
                        (0, 3, 4, 3),  # KPI Summary
                        (4, 3, 4, 3),  # Recent Activity
                        (8, 3, 4, 3),  # Critical Alerts
                    ]
                    
                    for i, (widget, (x, y, w, h)) in enumerate(zip(widgets, positions)):
                        DashboardWidgetPlacement.objects.create(
                            dashboard=dashboard,
                            widget=widget,
                            position_x=x,
                            position_y=y,
                            width=w,
                            height=h
                        )
            
            self.stdout.write('Created user dashboards with widget placements')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created sample data!\n'
                f'Admin user: {admin_email} / admin123\n'
                f'Demo users: john.smith@demo.com, sarah.johnson@demo.com, etc. / demo123\n'
                f'Tenant: {tenant_name}'
            )
        )