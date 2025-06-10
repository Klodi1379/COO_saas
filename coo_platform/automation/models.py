"""
Automation models for intelligent workflow automation.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import TimeStampedModel, UUIDModel
from tenants.models import TenantAwareModel
import json


class AutomationRule(UUIDModel, TenantAwareModel, TimeStampedModel):
    """
    Main automation rule that defines when and what actions to execute.
    """
    TRIGGER_TYPES = [
        ('kpi_threshold', 'KPI Threshold'),
        ('task_status', 'Task Status Change'),
        ('project_milestone', 'Project Milestone'),
        ('time_based', 'Time-based Schedule'),
        ('data_anomaly', 'Data Anomaly Detection'),
        ('user_action', 'User Action'),
        ('external_event', 'External Event'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('draft', 'Draft'),
        ('archived', 'Archived'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Trigger Configuration
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPES)
    trigger_config = models.JSONField(
        default=dict,
        help_text="JSON configuration for the trigger conditions"
    )
    
    # Execution Settings
    is_enabled = models.BooleanField(default=True)
    run_once = models.BooleanField(default=False, help_text="Execute only once when triggered")
    max_executions = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Maximum number of times this rule can execute"
    )
    execution_count = models.PositiveIntegerField(default=0)
    
    # Timing and Scheduling
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    next_check = models.DateTimeField(null=True, blank=True)
    
    # Ownership and Permissions
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rules')
    team_access = models.ManyToManyField(
        User,
        blank=True,
        related_name='accessible_rules',
        help_text="Users who can view and modify this rule"
    )
    
    # Advanced Settings
    priority = models.PositiveIntegerField(
        default=5,
        help_text="Execution priority (1=highest, 10=lowest)"
    )
    timeout_seconds = models.PositiveIntegerField(
        default=300,
        help_text="Maximum execution time in seconds"
    )
    
    class Meta:
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['tenant', 'status', 'is_enabled']),
            models.Index(fields=['trigger_type', 'next_check']),
            models.Index(fields=['created_by', 'status']),
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError('Start date must be before end date.')
        
        if self.max_executions and self.max_executions <= 0:
            raise ValidationError('Max executions must be greater than 0.')
    
    def can_execute(self):
        """Check if the rule can be executed."""
        if not self.is_enabled or self.status != 'active':
            return False
        
        # Check date constraints
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        
        # Check execution limits
        if self.max_executions and self.execution_count >= self.max_executions:
            return False
        
        return True
    
    def should_trigger(self):
        """Check if the rule should be triggered based on its conditions."""
        if not self.can_execute():
            return False
        
        # This method will be called by the automation engine
        # The actual trigger checking logic will be implemented based on trigger_type
        return self._check_trigger_conditions()
    
    def _check_trigger_conditions(self):
        """Check specific trigger conditions based on trigger type."""
        from kpis.models import SmartKPI, KPIDataPoint
        from projects.models import Task, Project
        
        if self.trigger_type == 'kpi_threshold':
            kpi_id = self.trigger_config.get('kpi_id')
            operator = self.trigger_config.get('operator')  # 'gt', 'lt', 'eq', 'gte', 'lte'
            threshold = self.trigger_config.get('threshold')
            
            if kpi_id and operator and threshold is not None:
                try:
                    kpi = SmartKPI.objects.get(id=kpi_id, tenant=self.tenant)
                    current_value = kpi.get_latest_value()
                    
                    if current_value is not None:
                        if operator == 'gt' and current_value > threshold:
                            return True
                        elif operator == 'lt' and current_value < threshold:
                            return True
                        elif operator == 'eq' and current_value == threshold:
                            return True
                        elif operator == 'gte' and current_value >= threshold:
                            return True
                        elif operator == 'lte' and current_value <= threshold:
                            return True
                except SmartKPI.DoesNotExist:
                    pass
        
        elif self.trigger_type == 'task_status':
            task_id = self.trigger_config.get('task_id')
            target_status = self.trigger_config.get('status')
            
            if task_id and target_status:
                try:
                    task = Task.objects.get(id=task_id, project__tenant=self.tenant)
                    return task.status == target_status
                except Task.DoesNotExist:
                    pass
        
        elif self.trigger_type == 'time_based':
            schedule = self.trigger_config.get('schedule')  # 'daily', 'weekly', 'monthly'
            time_of_day = self.trigger_config.get('time_of_day')  # HH:MM format
            
            if schedule and time_of_day:
                now = timezone.now()
                
                # Simple time-based checking (could be enhanced with cron-like syntax)
                if schedule == 'daily':
                    return now.strftime('%H:%M') == time_of_day
                # Add more schedule types as needed
        
        return False
    
    def execute(self):
        """Execute all actions associated with this rule."""
        if not self.can_execute():
            return False
        
        executed_actions = 0
        failed_actions = 0
        
        # Execute all associated actions
        for action in self.actions.filter(is_enabled=True).order_by('order'):
            try:
                success = action.execute()
                if success:
                    executed_actions += 1
                else:
                    failed_actions += 1
            except Exception as e:
                failed_actions += 1
                # Log the error
                AutomationLog.objects.create(
                    rule=self,
                    action=action,
                    status='error',
                    message=f'Action execution failed: {str(e)}'
                )
        
        # Update execution count and last triggered
        self.execution_count += 1
        self.last_triggered = timezone.now()
        self.save(update_fields=['execution_count', 'last_triggered'])
        
        # Log the overall execution
        AutomationLog.objects.create(
            rule=self,
            status='success' if failed_actions == 0 else 'partial',
            message=f'Executed {executed_actions} actions, {failed_actions} failed'
        )
        
        return failed_actions == 0


class AutomationAction(UUIDModel, TimeStampedModel):
    """
    Individual actions that can be executed by automation rules.
    """
    ACTION_TYPES = [
        ('send_email', 'Send Email'),
        ('send_notification', 'Send Notification'),
        ('create_task', 'Create Task'),
        ('update_task', 'Update Task Status'),
        ('send_slack_message', 'Send Slack Message'),
        ('webhook_call', 'Call Webhook'),
        ('create_kpi_datapoint', 'Create KPI Data Point'),
        ('generate_report', 'Generate Report'),
        ('assign_user', 'Assign User to Task/Project'),
        ('custom_script', 'Execute Custom Script'),
    ]
    
    rule = models.ForeignKey(
        AutomationRule, 
        on_delete=models.CASCADE, 
        related_name='actions'
    )
    
    # Action Configuration
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Action Parameters
    action_config = models.JSONField(
        default=dict,
        help_text="JSON configuration for the action parameters"
    )
    
    # Execution Settings
    is_enabled = models.BooleanField(default=True)
    order = models.PositiveIntegerField(
        default=1,
        help_text="Execution order within the rule"
    )
    continue_on_failure = models.BooleanField(
        default=True,
        help_text="Continue executing other actions if this one fails"
    )
    
    # Delay and Retry Settings
    delay_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Delay before executing this action"
    )
    max_retries = models.PositiveIntegerField(
        default=0,
        help_text="Number of retry attempts on failure"
    )
    retry_delay_seconds = models.PositiveIntegerField(
        default=60,
        help_text="Delay between retry attempts"
    )
    
    class Meta:
        ordering = ['order', 'name']
    
    def __str__(self):
        return f"{self.rule.name} - {self.name}"
    
    def execute(self):
        """Execute this specific action."""
        import time
        from core.utils import create_notification
        from django.core.mail import send_mail
        from django.conf import settings
        
        # Apply delay if specified
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        
        success = False
        attempts = 0
        max_attempts = self.max_retries + 1
        
        while attempts < max_attempts and not success:
            try:
                if self.action_type == 'send_email':
                    success = self._execute_send_email()
                elif self.action_type == 'send_notification':
                    success = self._execute_send_notification()
                elif self.action_type == 'create_task':
                    success = self._execute_create_task()
                elif self.action_type == 'update_task':
                    success = self._execute_update_task()
                elif self.action_type == 'webhook_call':
                    success = self._execute_webhook_call()
                elif self.action_type == 'create_kpi_datapoint':
                    success = self._execute_create_kpi_datapoint()
                else:
                    # Placeholder for other action types
                    success = True
                
                if success:
                    break
                    
            except Exception as e:
                success = False
                print(f"Action execution error: {e}")
            
            attempts += 1
            if attempts < max_attempts:
                time.sleep(self.retry_delay_seconds)
        
        return success
    
    def _execute_send_email(self):
        """Execute send email action."""
        config = self.action_config
        recipients = config.get('recipients', [])
        subject = config.get('subject', '')
        message = config.get('message', '')
        
        if recipients and subject and message:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False
            )
            return True
        return False
    
    def _execute_send_notification(self):
        """Execute send notification action."""
        config = self.action_config
        user_ids = config.get('user_ids', [])
        title = config.get('title', '')
        message = config.get('message', '')
        notification_type = config.get('type', 'info')
        
        if user_ids and title and message:
            from django.contrib.auth.models import User
            
            users = User.objects.filter(id__in=user_ids)
            for user in users:
                create_notification(
                    recipient=user,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    action_url=config.get('action_url', ''),
                    action_label=config.get('action_label', '')
                )
            return True
        return False
    
    def _execute_create_task(self):
        """Execute create task action."""
        from projects.models import Task, Project
        
        config = self.action_config
        project_id = config.get('project_id')
        title = config.get('title', '')
        description = config.get('description', '')
        assigned_to_id = config.get('assigned_to_id')
        
        if project_id and title:
            try:
                project = Project.objects.get(id=project_id, tenant=self.rule.tenant)
                
                task_data = {
                    'project': project,
                    'title': title,
                    'description': description,
                    'created_by': self.rule.created_by,
                    'priority': config.get('priority', 'medium'),
                    'status': config.get('status', 'todo'),
                }
                
                if assigned_to_id:
                    try:
                        assigned_to = User.objects.get(id=assigned_to_id)
                        task_data['assigned_to'] = assigned_to
                    except User.DoesNotExist:
                        pass
                
                Task.objects.create(**task_data)
                return True
            except Project.DoesNotExist:
                pass
        return False
    
    def _execute_update_task(self):
        """Execute update task status action."""
        from projects.models import Task
        
        config = self.action_config
        task_id = config.get('task_id')
        new_status = config.get('status')
        
        if task_id and new_status:
            try:
                task = Task.objects.get(id=task_id, project__tenant=self.rule.tenant)
                task.status = new_status
                task.save()
                return True
            except Task.DoesNotExist:
                pass
        return False
    
    def _execute_webhook_call(self):
        """Execute webhook call action."""
        import requests
        
        config = self.action_config
        url = config.get('url')
        method = config.get('method', 'POST')
        headers = config.get('headers', {})
        data = config.get('data', {})
        
        if url:
            try:
                if method.upper() == 'POST':
                    response = requests.post(url, json=data, headers=headers, timeout=30)
                elif method.upper() == 'GET':
                    response = requests.get(url, params=data, headers=headers, timeout=30)
                else:
                    return False
                
                return response.status_code < 400
            except requests.RequestException:
                return False
        return False
    
    def _execute_create_kpi_datapoint(self):
        """Execute create KPI data point action."""
        from kpis.models import SmartKPI, KPIDataPoint
        from decimal import Decimal
        
        config = self.action_config
        kpi_id = config.get('kpi_id')
        value = config.get('value')
        date_str = config.get('date')  # Optional, defaults to today
        
        if kpi_id and value is not None:
            try:
                kpi = SmartKPI.objects.get(id=kpi_id, tenant=self.rule.tenant)
                
                from datetime import datetime
                if date_str:
                    date = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    date = timezone.now().date()
                
                KPIDataPoint.objects.create(
                    kpi=kpi,
                    date=date,
                    value=Decimal(str(value)),
                    source='automation',
                    notes=f'Created by automation rule: {self.rule.name}'
                )
                return True
            except (SmartKPI.DoesNotExist, ValueError):
                pass
        return False


class AutomationLog(UUIDModel, TimeStampedModel):
    """
    Log of automation rule executions for monitoring and debugging.
    """
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('partial', 'Partial Success'),
        ('skipped', 'Skipped'),
    ]
    
    rule = models.ForeignKey(
        AutomationRule, 
        on_delete=models.CASCADE, 
        related_name='logs'
    )
    action = models.ForeignKey(
        AutomationAction, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='logs'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    message = models.TextField()
    execution_time_ms = models.PositiveIntegerField(null=True, blank=True)
    
    # Context data
    trigger_data = models.JSONField(default=dict, blank=True)
    result_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['rule', 'status', 'created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.rule.name} - {self.status} at {self.created_at}"


class AutomationSchedule(UUIDModel, TimeStampedModel):
    """
    Scheduling system for time-based automation rules.
    """
    FREQUENCY_CHOICES = [
        ('once', 'One Time'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Cron'),
    ]
    
    rule = models.OneToOneField(
        AutomationRule, 
        on_delete=models.CASCADE, 
        related_name='schedule'
    )
    
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    start_time = models.TimeField(help_text="Time of day to run (for recurring schedules)")
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Custom cron expression (for advanced scheduling)
    cron_expression = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Custom cron expression (when frequency is 'custom')"
    )
    
    # Date constraints
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Execution tracking
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField()
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['next_run']
    
    def __str__(self):
        return f"{self.rule.name} - {self.frequency}"
    
    def calculate_next_run(self):
        """Calculate the next execution time based on frequency."""
        from datetime import datetime, timedelta
        import pytz
        
        tz = pytz.timezone(self.timezone)
        now = timezone.now().astimezone(tz)
        
        if self.frequency == 'once':
            # For one-time execution, use start_date + start_time
            next_run = datetime.combine(self.start_date, self.start_time)
            next_run = tz.localize(next_run)
        elif self.frequency == 'daily':
            next_run = now.replace(
                hour=self.start_time.hour,
                minute=self.start_time.minute,
                second=0,
                microsecond=0
            )
            if next_run <= now:
                next_run += timedelta(days=1)
        elif self.frequency == 'weekly':
            # Add weekly logic
            next_run = now.replace(
                hour=self.start_time.hour,
                minute=self.start_time.minute,
                second=0,
                microsecond=0
            )
            days_ahead = 7 - now.weekday()
            if days_ahead <= 0 or (days_ahead == 7 and next_run <= now):
                days_ahead += 7
            next_run += timedelta(days=days_ahead)
        else:
            # Default to daily for other frequencies (can be enhanced)
            next_run = now.replace(
                hour=self.start_time.hour,
                minute=self.start_time.minute,
                second=0,
                microsecond=0
            ) + timedelta(days=1)
        
        # Convert back to UTC
        self.next_run = next_run.astimezone(pytz.UTC)
        self.save(update_fields=['next_run'])
        
        return self.next_run
