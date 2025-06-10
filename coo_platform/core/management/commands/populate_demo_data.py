"""
Enhanced management command to populate COO Platform with comprehensive demo data.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta
import random

from tenants.models import Tenant, TenantUser
from core.models import UserProfile
from projects.models import Project, ProjectCategory, Task, ProjectMembership
from kpis.models import SmartKPI, KPICategory, KPIDataPoint, KPIAlert
from automation.models import AutomationRule, AutomationAction


class Command(BaseCommand):
    help = 'Populate COO Platform with comprehensive demo data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-name',
            type=str,
            default='TechCorp Solutions',
            help='Name of the demo tenant'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset existing data before creating new demo data'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up comprehensive demo data...'))
        
        with transaction.atomic():
            if options['reset']:
                self.reset_data()
            
            # Get or create tenant
            tenant = self.get_or_create_tenant(options['tenant_name'])
            
            # Get or create admin user
            admin_user = self.get_or_create_admin_user(tenant)
            
            # Create demo users
            team_users = self.create_team_users(tenant)
            
            # Create demo data
            self.create_project_categories(tenant)
            self.create_kpi_categories(tenant)
            projects = self.create_demo_projects(tenant, admin_user, team_users)
            self.create_project_tasks(projects, team_users)
            kpis = self.create_demo_kpis(tenant, admin_user, team_users)
            self.create_kpi_data_points(kpis, admin_user)
            self.create_automation_rules(tenant, admin_user, kpis)
            
        self.stdout.write(
            self.style.SUCCESS(
                f'Demo data setup completed!\n'
                f'Tenant: {tenant.name}\n'
                f'Admin: {admin_user.email}\n'
                f'Dashboard: http://127.0.0.1:49000/dashboard/\n'
                f'KPIs: http://127.0.0.1:49000/kpis/\n'
                f'Automation: http://127.0.0.1:49000/automation/'
            )
        )
    
    def reset_data(self):
        """Reset existing demo data."""
        self.stdout.write('Resetting existing data...')
        
        # Keep the admin user, but remove other demo data
        User.objects.filter(email__contains='demo.').delete()
        Tenant.objects.filter(name__icontains='demo').delete()
        Tenant.objects.filter(name__icontains='corp').delete()
        
        self.stdout.write('Data reset completed')
    
    def get_or_create_tenant(self, tenant_name):
        """Get or create demo tenant."""
        tenant, created = Tenant.objects.get_or_create(
            name=tenant_name,
            defaults={
                'contact_email': 'contact@techcorp.demo',
                'subscription_tier': 'professional',
                'status': 'active',
                'max_users': 25,
                'max_projects': 50,
                'max_storage_mb': 1000,
                'primary_color': '#1e40af',
                'secondary_color': '#64748b',
                'settings': {
                    'timezone': 'UTC',
                    'date_format': 'Y-m-d',
                    'currency': 'USD'
                },
                'features': ['advanced_analytics', 'automation', 'api_access']
            }
        )
        
        if created:
            self.stdout.write(f'Created tenant: {tenant.name}')
        else:
            self.stdout.write(f'Using existing tenant: {tenant.name}')
        
        return tenant
    
    def get_or_create_admin_user(self, tenant):
        """Get existing admin user or create one."""
        # First try to find existing admin user
        admin_user = User.objects.filter(is_superuser=True).first()
        
        if not admin_user:
            # Create new admin user
            admin_user = User.objects.create_user(
                username='demo_admin',
                email='demo.admin@techcorp.demo',
                password='admin123',
                first_name='Demo',
                last_name='Admin',
                is_staff=True,
                is_superuser=True
            )
            self.stdout.write(f'Created admin user: {admin_user.email}')
        else:
            self.stdout.write(f'Using existing admin user: {admin_user.email}')
        
        # Create or update user profile
        profile, created = UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={
                'role': 'consultant',
                'subscription_tier': 'professional',
                'email_notifications': True,
                'browser_notifications': True
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
        
        return admin_user
    
    def create_team_users(self, tenant):
        """Create demo team users."""
        team_data = [
            ('john.doe@techcorp.demo', 'John', 'Doe', 'Product Manager', 'manager'),
            ('sarah.wilson@techcorp.demo', 'Sarah', 'Wilson', 'Operations Director', 'admin'),
            ('mike.chen@techcorp.demo', 'Mike', 'Chen', 'Lead Developer', 'user'),
            ('lisa.garcia@techcorp.demo', 'Lisa', 'Garcia', 'Marketing Manager', 'user'),
            ('david.brown@techcorp.demo', 'David', 'Brown', 'Sales Director', 'manager'),
        ]
        
        team_users = []
        for email, first_name, last_name, title, role in team_data:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email.split('@')[0].replace('.', '_'),
                    'first_name': first_name,
                    'last_name': last_name,
                }
            )
            
            if created:
                user.set_password('demo123')
                user.save()
                self.stdout.write(f'Created user: {user.get_full_name()}')
            
            # Create profile
            UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': 'client_user',
                    'job_title': title,
                    'email_notifications': True
                }
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
                    'can_export_data': role in ['owner', 'admin'],
                }
            )
            
            team_users.append(user)
        
        self.stdout.write(f'Created {len(team_users)} team users')
        return team_users
    
    def create_project_categories(self, tenant):
        """Create project categories."""
        categories = [
            ('Product Development', 'New product features and enhancements', '#3b82f6', 'fas fa-laptop-code'),
            ('Marketing & Sales', 'Marketing campaigns and sales initiatives', '#10b981', 'fas fa-bullhorn'),
            ('Operations', 'Operational improvements and process optimization', '#f59e0b', 'fas fa-cogs'),
            ('Customer Success', 'Customer support and satisfaction projects', '#8b5cf6', 'fas fa-users'),
            ('Infrastructure', 'IT infrastructure and technical improvements', '#ef4444', 'fas fa-server'),
        ]
        
        for name, description, color, icon in categories:
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
            ('Financial Performance', 'financial', 'Revenue, costs, and profitability metrics', '#10b981', 'fas fa-dollar-sign'),
            ('Customer Metrics', 'customer', 'Customer satisfaction and engagement', '#3b82f6', 'fas fa-users'),
            ('Operational Excellence', 'operational', 'Efficiency and process performance', '#f59e0b', 'fas fa-cogs'),
            ('Growth & Scale', 'growth', 'Business growth and expansion metrics', '#ef4444', 'fas fa-chart-line'),
            ('Team Performance', 'team', 'Team productivity and engagement', '#8b5cf6', 'fas fa-user-friends'),
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
        categories = list(ProjectCategory.objects.filter(tenant=tenant))
        
        projects_data = [
            {
                'name': 'Mobile App V2.0',
                'description': 'Complete redesign and development of mobile application with enhanced UX',
                'status': 'active',
                'priority': 'high',
                'progress': 75,
                'budget': 150000,
                'spent': 112500,
                'category_index': 0,  # Product Development
            },
            {
                'name': 'Q2 Digital Marketing Campaign',
                'description': 'Multi-channel digital marketing campaign for Q2 product launches',
                'status': 'active',
                'priority': 'medium',
                'progress': 45,
                'budget': 80000,
                'spent': 36000,
                'category_index': 1,  # Marketing & Sales
            },
            {
                'name': 'Customer Support Portal',
                'description': 'Self-service customer support portal with AI chatbot integration',
                'status': 'planning',
                'priority': 'medium',
                'progress': 15,
                'budget': 75000,
                'spent': 11250,
                'category_index': 3,  # Customer Success
            },
            {
                'name': 'Process Automation Initiative',
                'description': 'Automate manual processes across operations using RPA and AI',
                'status': 'active',
                'priority': 'high',
                'progress': 60,
                'budget': 200000,
                'spent': 120000,
                'category_index': 2,  # Operations
            },
            {
                'name': 'Cloud Infrastructure Migration',
                'description': 'Migration from on-premise to cloud infrastructure for scalability',
                'status': 'completed',
                'priority': 'critical',
                'progress': 100,
                'budget': 120000,
                'spent': 115000,
                'category_index': 4,  # Infrastructure
            },
            {
                'name': 'AI Analytics Dashboard',
                'description': 'Advanced analytics dashboard with AI-powered insights',
                'status': 'active',
                'priority': 'high',
                'progress': 35,
                'budget': 90000,
                'spent': 31500,
                'category_index': 0,  # Product Development
            },
        ]
        
        projects = []
        for project_data in projects_data:
            project = Project.objects.create(
                tenant=tenant,
                name=project_data['name'],
                description=project_data['description'],
                status=project_data['status'],
                priority=project_data['priority'],
                progress_percentage=project_data['progress'],
                category=categories[project_data['category_index']] if categories else None,
                project_manager=random.choice([admin_user] + team_users[:3]),
                start_date=date.today() - timedelta(days=random.randint(30, 120)),
                target_end_date=date.today() + timedelta(days=random.randint(30, 180)),
                budget_allocated=Decimal(project_data['budget']),
                budget_spent=Decimal(project_data['spent']),
            )
            
            # Add team members
            for user in random.sample(team_users, random.randint(2, 4)):
                ProjectMembership.objects.get_or_create(
                    project=project,
                    user=user,
                    defaults={
                        'role': random.choice(['developer', 'designer', 'analyst', 'tester']),
                        'can_manage_tasks': random.choice([True, False]),
                    }
                )
            
            projects.append(project)
        
        self.stdout.write(f'Created {len(projects)} projects')
        return projects
    
    def create_project_tasks(self, projects, team_users):
        """Create tasks for projects."""
        task_templates = [
            ('Requirements Analysis', 'completed', 'high'),
            ('Technical Design', 'completed', 'high'), 
            ('Development Phase 1', 'in_progress', 'high'),
            ('Development Phase 2', 'todo', 'medium'),
            ('Quality Assurance Testing', 'todo', 'high'),
            ('User Acceptance Testing', 'todo', 'medium'),
            ('Documentation', 'in_progress', 'low'),
            ('Deployment Planning', 'todo', 'medium'),
            ('Production Deployment', 'todo', 'high'),
            ('Post-Launch Monitoring', 'todo', 'low'),
        ]
        
        total_tasks = 0
        for project in projects:
            # Number of tasks based on project complexity
            num_tasks = random.randint(5, 8)
            selected_tasks = random.sample(task_templates, num_tasks)
            
            for i, (title, status, priority) in enumerate(selected_tasks):
                # Adjust status based on project progress
                if project.progress_percentage == 100:
                    status = 'completed'
                elif project.progress_percentage > 70 and i < 3:
                    status = 'completed'
                elif project.progress_percentage > 40 and i < 2:
                    status = 'completed'
                elif project.status == 'planning':
                    status = 'todo'
                
                Task.objects.create(
                    project=project,
                    title=f'{title} - {project.name}',
                    description=f'Task for {title} in the {project.name} project',
                    status=status,
                    priority=priority,
                    assigned_to=random.choice(team_users),
                    created_by=project.project_manager,
                    due_date=timezone.now() + timedelta(days=random.randint(1, 60)),
                    estimated_hours=Decimal(random.randint(8, 40)),
                    actual_hours=Decimal(random.randint(5, 35)) if status == 'completed' else Decimal(0),
                )
                total_tasks += 1
        
        self.stdout.write(f'Created {total_tasks} tasks')
    
    def create_demo_kpis(self, tenant, admin_user, team_users):
        """Create demo KPIs."""
        categories = {cat.category_type: cat for cat in KPICategory.objects.filter(tenant=tenant)}
        
        kpis_data = [
            # Financial KPIs
            {
                'name': 'Monthly Recurring Revenue',
                'category': 'financial',
                'unit': '$',
                'target': 250000,
                'warning': 225000,
                'critical': 200000,
                'trend': 'up_good',
                'chart_type': 'line',
                'values': [235000, 242000, 248000, 255000, 262000, 258000],
            },
            {
                'name': 'Customer Acquisition Cost',
                'category': 'financial',
                'unit': '$',
                'target': 150,
                'warning': 175,
                'critical': 200,
                'trend': 'down_good',
                'chart_type': 'bar',
                'values': [165, 158, 152, 148, 145, 150],
            },
            # Customer KPIs
            {
                'name': 'Net Promoter Score',
                'category': 'customer',
                'unit': 'score',
                'target': 50,
                'warning': 40,
                'critical': 30,
                'trend': 'up_good',
                'chart_type': 'gauge',
                'values': [45, 47, 48, 52, 54, 51],
            },
            {
                'name': 'Customer Satisfaction Rate',
                'category': 'customer',
                'unit': '%',
                'target': 90,
                'warning': 85,
                'critical': 80,
                'trend': 'up_good',
                'chart_type': 'line',
                'values': [87, 89, 91, 93, 91, 92],
            },
            # Operational KPIs
            {
                'name': 'Average Response Time',
                'category': 'operational',
                'unit': 'hours',
                'target': 4,
                'warning': 6,
                'critical': 8,
                'trend': 'down_good',
                'chart_type': 'area',
                'values': [6.5, 5.8, 5.2, 4.5, 3.8, 4.2],
            },
            {
                'name': 'Process Efficiency Rate',
                'category': 'operational',
                'unit': '%',
                'target': 95,
                'warning': 90,
                'critical': 85,
                'trend': 'up_good',
                'chart_type': 'line',
                'values': [88, 91, 93, 95, 97, 94],
            },
            # Growth KPIs
            {
                'name': 'Monthly Active Users',
                'category': 'growth',
                'unit': 'users',
                'target': 15000,
                'warning': 12000,
                'critical': 10000,
                'trend': 'up_good',
                'chart_type': 'line',
                'values': [12500, 13200, 14100, 15500, 16200, 15800],
            },
            {
                'name': 'Conversion Rate',
                'category': 'growth',
                'unit': '%',
                'target': 3.5,
                'warning': 3.0,
                'critical': 2.5,
                'trend': 'up_good',
                'chart_type': 'bar',
                'values': [2.8, 3.1, 3.3, 3.6, 3.8, 3.5],
            },
            # Team KPIs
            {
                'name': 'Employee Satisfaction',
                'category': 'team',
                'unit': 'score',
                'target': 4.5,
                'warning': 4.0,
                'critical': 3.5,
                'trend': 'up_good',
                'chart_type': 'gauge',
                'values': [4.1, 4.2, 4.3, 4.5, 4.6, 4.4],
            },
            {
                'name': 'Team Productivity Index',
                'category': 'team',
                'unit': 'index',
                'target': 100,
                'warning': 90,
                'critical': 80,
                'trend': 'up_good',
                'chart_type': 'line',
                'values': [92, 95, 98, 102, 105, 103],
            },
        ]
        
        kpis = []
        for kpi_data in kpis_data:
            category = categories.get(kpi_data['category'])
            owner = random.choice([admin_user] + team_users[:3])
            
            kpi = SmartKPI.objects.create(
                tenant=tenant,
                name=kpi_data['name'],
                description=f'Demo KPI tracking {kpi_data["name"]} for business performance monitoring',
                category=category,
                data_source_type='manual',
                unit=kpi_data['unit'],
                target_value=Decimal(str(kpi_data['target'])),
                warning_threshold=Decimal(str(kpi_data['warning'])),
                critical_threshold=Decimal(str(kpi_data['critical'])),
                trend_direction=kpi_data['trend'],
                chart_type=kpi_data['chart_type'],
                owner=owner,
                is_featured=True,
                is_active=True,
                auto_update_frequency='weekly',
            )
            
            # Add stakeholders
            stakeholders = random.sample(team_users, random.randint(1, 3))
            kpi.stakeholders.set(stakeholders)
            
            kpis.append((kpi, kpi_data['values']))
        
        self.stdout.write(f'Created {len(kpis)} KPIs')
        return kpis
    
    def create_kpi_data_points(self, kpis, admin_user):
        """Create historical data points for KPIs."""
        total_points = 0
        
        for kpi, values in kpis:
            # Create weekly data points for the last 6 weeks
            for i, value in enumerate(values):
                weeks_ago = len(values) - i - 1
                data_date = date.today() - timedelta(weeks=weeks_ago)
                
                KPIDataPoint.objects.create(
                    kpi=kpi,
                    date=data_date,
                    value=Decimal(str(value)),
                    source='demo',
                    entered_by=admin_user,
                    notes=f'Demo data point for week {i+1}',
                )
                total_points += 1
                
                # Create alerts for critical values
                if ((kpi.trend_direction == 'up_good' and value < float(kpi.critical_threshold)) or
                    (kpi.trend_direction == 'down_good' and value > float(kpi.critical_threshold))):
                    
                    KPIAlert.objects.create(
                        kpi=kpi,
                        title=f'{kpi.name} Critical Alert',
                        message=f'{kpi.name} has reached critical threshold: {value} {kpi.unit}',
                        severity='critical',
                        threshold_value=kpi.critical_threshold,
                        actual_value=Decimal(str(value)),
                        is_resolved=random.choice([True, False]),
                    )
        
        self.stdout.write(f'Created {total_points} KPI data points')
    
    def create_automation_rules(self, tenant, admin_user, kpis):
        """Create automation rules."""
        # Get some KPIs for automation
        kpi_list = [kpi for kpi, _ in kpis[:3]]  # Use first 3 KPIs
        
        rules_data = [
            {
                'name': 'Revenue Drop Alert',
                'description': 'Send alert when monthly revenue drops below warning threshold',
                'trigger_type': 'kpi_threshold',
                'kpi': kpi_list[0] if kpi_list else None,
                'actions': [
                    {
                        'name': 'Send Email Alert',
                        'action_type': 'send_email',
                        'config': {
                            'recipients': ['management@techcorp.demo'],
                            'subject': 'Revenue Alert',
                            'message': 'Monthly revenue has dropped below warning threshold.'
                        }
                    }
                ]
            },
            {
                'name': 'Customer Satisfaction Monitoring',
                'description': 'Monitor customer satisfaction and trigger actions when it drops',
                'trigger_type': 'kpi_threshold',
                'kpi': kpi_list[1] if len(kpi_list) > 1 else None,
                'actions': [
                    {
                        'name': 'Create Support Ticket',
                        'action_type': 'create_task',
                        'config': {
                            'title': 'Investigate Customer Satisfaction Drop',
                            'priority': 'high',
                            'assigned_to': 'customer_success_team'
                        }
                    }
                ]
            },
            {
                'name': 'Performance Optimization',
                'description': 'Automatically trigger performance review when response time exceeds threshold',
                'trigger_type': 'kpi_threshold',
                'kpi': kpi_list[2] if len(kpi_list) > 2 else None,
                'actions': [
                    {
                        'name': 'Schedule Performance Review',
                        'action_type': 'schedule_meeting',
                        'config': {
                            'meeting_type': 'performance_review',
                            'attendees': ['operations_team'],
                            'duration': 60
                        }
                    }
                ]
            },
        ]
        
        for rule_data in rules_data:
            if not rule_data['kpi']:
                continue
                
            rule = AutomationRule.objects.create(
                tenant=tenant,
                name=rule_data['name'],
                description=rule_data['description'],
                trigger_type=rule_data['trigger_type'],
                trigger_config={
                    'kpi_id': str(rule_data['kpi'].id),
                    'operator': 'lt' if rule_data['kpi'].trend_direction == 'up_good' else 'gt',
                    'threshold': float(rule_data['kpi'].warning_threshold)
                },
                status='active',
                is_enabled=True,
                created_by=admin_user,
                priority=random.randint(1, 5),
            )
            
            # Add actions
            for i, action_data in enumerate(rule_data['actions']):
                AutomationAction.objects.create(
                    rule=rule,
                    name=action_data['name'],
                    action_type=action_data['action_type'],
                    action_config=action_data['config'],
                    order=i + 1,
                )
        
        self.stdout.write(f'Created {len(rules_data)} automation rules')
