"""
Management command to set up demo data for COO Platform.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
import random

from tenants.models import Tenant, TenantUser
from core.models import UserProfile
from projects.models import Project, ProjectCategory, Task, ProjectMembership
from kpis.models import SmartKPI, KPICategory, KPIDataPoint
from automation.models import AutomationRule, AutomationAction


class Command(BaseCommand):
    help = 'Set up demo data for COO Platform'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-name',
            type=str,
            default='Demo Company',
            help='Name of the demo tenant'
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@demo.com',
            help='Email for the demo admin user'
        )
        parser.add_argument(
            '--skip-users',
            action='store_true',
            help='Skip creating demo users'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up demo data...'))
        
        # Create demo tenant
        tenant = self.create_demo_tenant(options['tenant_name'])
        
        # Create demo users
        if not options['skip_users']:
            admin_user, team_users = self.create_demo_users(tenant, options['admin_email'])
        else:
            admin_user = User.objects.first()
            team_users = User.objects.all()[:3]
        
        # Create demo data
        self.create_project_categories(tenant)
        self.create_kpi_categories(tenant)
        self.create_demo_projects(tenant, admin_user, team_users)
        self.create_demo_kpis(tenant, admin_user)
        self.create_demo_automation(tenant, admin_user)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Demo data setup completed for tenant: {tenant.name}\n'
                f'Admin user: {admin_user.email if admin_user else "Not created"}\n'
                f'Dashboard URL: http://localhost:8000/dashboard/'
            )
        )
    
    def create_demo_tenant(self, tenant_name):
        """Create demo tenant."""
        tenant, created = Tenant.objects.get_or_create(
            name=tenant_name,
            defaults={
                'contact_email': 'contact@demo.com',
                'subscription_tier': 'professional',
                'status': 'active',
                'max_users': 15,
                'max_projects': 25,
            }
        )
        
        if created:
            self.stdout.write(f'Created tenant: {tenant.name}')
        else:
            self.stdout.write(f'Using existing tenant: {tenant.name}')
        
        return tenant
    
    def create_demo_users(self, tenant, admin_email):
        """Create demo users."""
        # Create admin user
        admin_user, created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                'username': 'admin',
                'first_name': 'Admin',
                'last_name': 'User',
                'is_staff': True,
                'is_superuser': True,
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
                'role': 'consultant',
                'subscription_tier': 'professional',
            }
        )
        
        # Create tenant relationship
        TenantUser.objects.get_or_create(
            tenant=tenant,
            user=admin_user,
            defaults={
                'role': 'owner',
                'can_invite_users': True,
                'can_manage_projects': True,
                'can_manage_kpis': True,
                'can_view_analytics': True,
                'can_export_data': True,
            }
        )
        
        # Create team users
        team_users = []
        team_data = [
            ('john@demo.com', 'John', 'Smith', 'manager'),
            ('sarah@demo.com', 'Sarah', 'Johnson', 'admin'),
            ('mike@demo.com', 'Mike', 'Brown', 'user'),
        ]
        
        for email, first_name, last_name, role in team_data:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email.split('@')[0],
                    'first_name': first_name,
                    'last_name': last_name,
                }
            )
            
            if created:
                user.set_password('demo123')
                user.save()
                self.stdout.write(f'Created user: {user.email}')
            
            # Create profile
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': 'client_user'}
            )
            
            # Create tenant relationship
            TenantUser.objects.get_or_create(
                tenant=tenant,
                user=user,
                defaults={
                    'role': role,
                    'can_manage_projects': role in ['owner', 'admin', 'manager'],
                    'can_manage_kpis': role in ['owner', 'admin', 'manager'],
                    'can_view_analytics': True,
                }
            )
            
            team_users.append(user)
        
        return admin_user, team_users
    
    def create_project_categories(self, tenant):
        """Create project categories."""
        categories = [
            ('Development', 'Software development projects', '#007bff'),
            ('Marketing', 'Marketing and promotion projects', '#28a745'),
            ('Operations', 'Operational improvement projects', '#ffc107'),
            ('Strategy', 'Strategic planning projects', '#dc3545'),
        ]
        
        for name, description, color in categories:
            ProjectCategory.objects.get_or_create(
                tenant=tenant,
                name=name,
                defaults={
                    'description': description,
                    'color': color,
                }
            )
        
        self.stdout.write('Created project categories')
    
    def create_kpi_categories(self, tenant):
        """Create KPI categories."""
        categories = [
            ('Financial', 'financial', 'Financial performance metrics', '#28a745', 'fas fa-dollar-sign'),
            ('Customer', 'customer', 'Customer satisfaction and engagement', '#007bff', 'fas fa-users'),
            ('Operational', 'operational', 'Operational efficiency metrics', '#ffc107', 'fas fa-cogs'),
            ('Growth', 'growth', 'Business growth indicators', '#dc3545', 'fas fa-chart-line'),
        ]
        
        for name, category_type, description, color, icon in categories:
            KPICategory.objects.get_or_create(
                tenant=tenant,
                name=name,
                defaults={
                    'category_type': category_type,
                    'description': description,
                    'color': color,
                    'icon': icon,
                }
            )
        
        self.stdout.write('Created KPI categories')
    
    def create_demo_projects(self, tenant, admin_user, team_users):
        """Create demo projects."""
        categories = ProjectCategory.objects.filter(tenant=tenant)
        
        projects_data = [
            {
                'name': 'Website Redesign',
                'description': 'Complete redesign of company website with modern UI/UX',
                'status': 'active',
                'priority': 'high',
                'progress': 65,
            },
            {
                'name': 'Customer Support System',
                'description': 'Implementation of new customer support ticketing system',
                'status': 'active',
                'priority': 'medium',
                'progress': 30,
            },
            {
                'name': 'Q1 Marketing Campaign',
                'description': 'Digital marketing campaign for Q1 product launch',
                'status': 'completed',
                'priority': 'high',
                'progress': 100,
            },
            {
                'name': 'Inventory Management',
                'description': 'Streamline inventory management processes',
                'status': 'planning',
                'priority': 'medium',
                'progress': 10,
            },
        ]
        
        for project_data in projects_data:
            project = Project.objects.create(
                tenant=tenant,
                name=project_data['name'],
                description=project_data['description'],
                status=project_data['status'],
                priority=project_data['priority'],
                progress_percentage=project_data['progress'],
                category=random.choice(categories) if categories else None,
                project_manager=admin_user,
                start_date=date.today() - timedelta(days=random.randint(10, 60)),
                target_end_date=date.today() + timedelta(days=random.randint(30, 90)),
                budget_allocated=Decimal(random.randint(10000, 100000)),
                budget_spent=Decimal(random.randint(1000, 50000)),
            )
            
            # Add team members
            for i, user in enumerate(team_users[:2]):
                ProjectMembership.objects.create(
                    project=project,
                    user=user,
                    role=random.choice(['developer', 'designer', 'manager']),
                    can_manage_tasks=i == 0,
                )
            
            # Create demo tasks
            self.create_demo_tasks(project, team_users)
        
        self.stdout.write('Created demo projects')
    
    def create_demo_tasks(self, project, team_users):
        """Create demo tasks for a project."""
        tasks_data = [
            ('Setup development environment', 'completed'),
            ('Create wireframes', 'completed'),
            ('Implement user authentication', 'in_progress'),
            ('Design homepage layout', 'in_progress'),
            ('Write documentation', 'todo'),
            ('Conduct user testing', 'todo'),
        ]
        
        for i, (title, status) in enumerate(tasks_data[:4]):  # Limit to 4 tasks per project
            Task.objects.create(
                project=project,
                title=title,
                description=f'Task description for {title}',
                status=status,
                priority=random.choice(['low', 'medium', 'high']),
                assigned_to=random.choice(team_users) if team_users else None,
                created_by=project.project_manager,
                due_date=timezone.now() + timedelta(days=random.randint(1, 30)),
                estimated_hours=Decimal(random.randint(4, 24)),
            )
    
    def create_demo_kpis(self, tenant, admin_user):
        """Create demo KPIs."""
        categories = KPICategory.objects.filter(tenant=tenant)
        
        kpis_data = [
            {
                'name': 'Monthly Revenue',
                'category_type': 'financial',
                'unit': '$',
                'target': 50000,
                'warning': 45000,
                'critical': 40000,
                'trend': 'up_good',
                'values': [45000, 47000, 49000, 51000, 53000],
            },
            {
                'name': 'Customer Satisfaction Score',
                'category_type': 'customer',
                'unit': '%',
                'target': 90,
                'warning': 85,
                'critical': 80,
                'trend': 'up_good',
                'values': [88, 89, 87, 91, 92],
            },
            {
                'name': 'Order Processing Time',
                'category_type': 'operational',
                'unit': 'hours',
                'target': 24,
                'warning': 30,
                'critical': 36,
                'trend': 'down_good',
                'values': [32, 28, 26, 25, 23],
            },
            {
                'name': 'Website Traffic',
                'category_type': 'growth',
                'unit': 'visitors',
                'target': 10000,
                'warning': 8000,
                'critical': 6000,
                'trend': 'up_good',
                'values': [8500, 9200, 9800, 10500, 11200],
            },
        ]
        
        for kpi_data in kpis_data:
            # Find matching category
            category = categories.filter(category_type=kpi_data['category_type']).first()
            
            kpi = SmartKPI.objects.create(
                tenant=tenant,
                name=kpi_data['name'],
                description=f'Demo KPI for {kpi_data["name"]}',
                category=category,
                data_source_type='manual',
                unit=kpi_data['unit'],
                target_value=Decimal(kpi_data['target']),
                warning_threshold=Decimal(kpi_data['warning']),
                critical_threshold=Decimal(kpi_data['critical']),
                trend_direction=kpi_data['trend'],
                owner=admin_user,
                is_featured=True,
            )
            
            # Add historical data points
            for i, value in enumerate(kpi_data['values']):
                KPIDataPoint.objects.create(
                    kpi=kpi,
                    date=date.today() - timedelta(days=(len(kpi_data['values']) - i - 1) * 7),
                    value=Decimal(value),
                    source='demo',
                    entered_by=admin_user,
                    notes='Demo data point',
                )
        
        self.stdout.write('Created demo KPIs with historical data')
    
    def create_demo_automation(self, tenant, admin_user):
        """Create demo automation rules."""
        # Create a simple automation rule
        rule = AutomationRule.objects.create(
            tenant=tenant,
            name='Low Revenue Alert',
            description='Send alert when monthly revenue drops below threshold',
            trigger_type='kpi_threshold',
            trigger_config={
                'kpi_name': 'Monthly Revenue',
                'operator': 'lt',
                'threshold': 45000
            },
            status='active',
            created_by=admin_user,
        )
        
        # Add action
        AutomationAction.objects.create(
            rule=rule,
            name='Send Email Alert',
            action_type='send_email',
            action_config={
                'recipients': [admin_user.email],
                'subject': 'Revenue Alert',
                'message': 'Monthly revenue has dropped below the warning threshold.'
            },
            order=1,
        )
        
        self.stdout.write('Created demo automation rules')
