"""
Serializers for the REST API.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from projects.models import Project, Task, ProjectCategory, ProjectMembership
from kpis.models import SmartKPI, KPIDataPoint, KPICategory, KPIAlert
from automation.models import AutomationRule, AutomationAction
from tenants.models import Tenant, TenantUser
from core.models import UserProfile, Notification


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profiles."""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'role', 'phone', 'avatar', 'subscription_tier',
            'timezone', 'email_notifications', 'full_name'
        ]
        read_only_fields = ['subscription_tier']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class UserSerializer(serializers.ModelSerializer):
    """Serializer for users."""
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']
        read_only_fields = ['id', 'username']


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for tenants."""
    user_count = serializers.ReadOnlyField()
    project_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'subscription_tier', 'status',
            'user_count', 'project_count', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at']


class ProjectCategorySerializer(serializers.ModelSerializer):
    """Serializer for project categories."""
    project_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectCategory
        fields = ['id', 'name', 'description', 'color', 'is_active', 'project_count']
    
    def get_project_count(self, obj):
        return obj.projects.filter(tenant=obj.tenant).count()


class ProjectMembershipSerializer(serializers.ModelSerializer):
    """Serializer for project memberships."""
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True
    )
    
    class Meta:
        model = ProjectMembership
        fields = [
            'id', 'user', 'user_id', 'role', 'is_active',
            'can_edit_project', 'can_manage_tasks', 'can_invite_members',
            'joined_date'
        ]


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for tasks."""
    assigned_to = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='assigned_to',
        write_only=True,
        required=False,
        allow_null=True
    )
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'status', 'priority',
            'assigned_to', 'assigned_to_id', 'created_by',
            'due_date', 'started_at', 'completed_at',
            'estimated_hours', 'actual_hours', 'tags',
            'is_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for projects."""
    category = ProjectCategorySerializer(read_only=True)
    project_manager = UserSerializer(read_only=True)
    team_members = UserSerializer(many=True, read_only=True)
    
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=ProjectCategory.objects.all(),
        source='category',
        write_only=True,
        required=False,
        allow_null=True
    )
    project_manager_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='project_manager',
        write_only=True,
        required=False,
        allow_null=True
    )
    
    # Computed fields
    is_overdue = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    budget_remaining = serializers.ReadOnlyField()
    budget_utilization = serializers.ReadOnlyField()
    
    # Task statistics
    task_count = serializers.SerializerMethodField()
    completed_tasks = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'status', 'priority',
            'category', 'category_id', 'project_manager', 'project_manager_id',
            'team_members', 'start_date', 'target_end_date', 'actual_end_date',
            'budget_allocated', 'budget_spent', 'progress_percentage',
            'tags', 'is_overdue', 'days_remaining', 'budget_remaining',
            'budget_utilization', 'task_count', 'completed_tasks',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_task_count(self, obj):
        return obj.tasks.count()
    
    def get_completed_tasks(self, obj):
        return obj.tasks.filter(status='completed').count()


class KPICategorySerializer(serializers.ModelSerializer):
    """Serializer for KPI categories."""
    kpi_count = serializers.ReadOnlyField()
    
    class Meta:
        model = KPICategory
        fields = [
            'id', 'name', 'category_type', 'description', 'color',
            'icon', 'is_active', 'display_order', 'kpi_count'
        ]


class KPIDataPointSerializer(serializers.ModelSerializer):
    """Serializer for KPI data points."""
    entered_by = UserSerializer(read_only=True)
    formatted_value = serializers.ReadOnlyField()
    
    class Meta:
        model = KPIDataPoint
        fields = [
            'id', 'date', 'value', 'formatted_value', 'source',
            'entered_by', 'notes', 'is_estimated', 'confidence_level',
            'created_at'
        ]
        read_only_fields = ['id', 'entered_by', 'created_at']


class SmartKPISerializer(serializers.ModelSerializer):
    """Serializer for Smart KPIs."""
    category = KPICategorySerializer(read_only=True)
    owner = UserSerializer(read_only=True)
    stakeholders = UserSerializer(many=True, read_only=True)
    
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=KPICategory.objects.all(),
        source='category',
        write_only=True,
        required=False,
        allow_null=True
    )
    owner_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='owner',
        write_only=True,
        required=False,
        allow_null=True
    )
    
    # Computed fields
    current_value = serializers.SerializerMethodField()
    performance_status = serializers.SerializerMethodField()
    trend_data = serializers.SerializerMethodField()
    
    class Meta:
        model = SmartKPI
        fields = [
            'id', 'name', 'description', 'category', 'category_id',
            'data_source_type', 'calculation_method', 'unit', 'decimal_places',
            'target_value', 'warning_threshold', 'critical_threshold',
            'trend_direction', 'auto_update_frequency', 'owner', 'owner_id',
            'stakeholders', 'is_active', 'is_featured', 'chart_type',
            'current_value', 'performance_status', 'trend_data',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_current_value(self, obj):
        value = obj.get_latest_value()
        return float(value) if value is not None else None
    
    def get_performance_status(self, obj):
        return obj.calculate_performance_status()
    
    def get_trend_data(self, obj):
        # Return last 30 days of trend data
        return obj.get_trend_data(days=30)


class KPIAlertSerializer(serializers.ModelSerializer):
    """Serializer for KPI alerts."""
    kpi = SmartKPISerializer(read_only=True)
    acknowledged_by = UserSerializer(read_only=True)
    
    class Meta:
        model = KPIAlert
        fields = [
            'id', 'kpi', 'alert_type', 'severity', 'title', 'message',
            'trigger_value', 'threshold_value', 'is_acknowledged',
            'acknowledged_by', 'acknowledged_at', 'is_resolved',
            'resolved_at', 'created_at'
        ]
        read_only_fields = ['id', 'acknowledged_by', 'created_at']


class AutomationActionSerializer(serializers.ModelSerializer):
    """Serializer for automation actions."""
    
    class Meta:
        model = AutomationAction
        fields = [
            'id', 'name', 'description', 'action_type', 'action_config',
            'is_enabled', 'order', 'continue_on_failure',
            'delay_seconds', 'max_retries', 'retry_delay_seconds'
        ]


class AutomationRuleSerializer(serializers.ModelSerializer):
    """Serializer for automation rules."""
    created_by = UserSerializer(read_only=True)
    team_access = UserSerializer(many=True, read_only=True)
    actions = AutomationActionSerializer(many=True, read_only=True)
    
    execution_stats = serializers.SerializerMethodField()
    can_execute = serializers.SerializerMethodField()
    
    class Meta:
        model = AutomationRule
        fields = [
            'id', 'name', 'description', 'status', 'trigger_type',
            'trigger_config', 'is_enabled', 'run_once', 'max_executions',
            'execution_count', 'start_date', 'end_date', 'last_triggered',
            'created_by', 'team_access', 'priority', 'actions',
            'execution_stats', 'can_execute', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'execution_count', 'last_triggered', 'created_by',
            'created_at', 'updated_at'
        ]
    
    def get_execution_stats(self, obj):
        logs = obj.logs.all()
        return {
            'total': logs.count(),
            'success': logs.filter(status='success').count(),
            'error': logs.filter(status='error').count(),
            'partial': logs.filter(status='partial').count(),
        }
    
    def get_can_execute(self, obj):
        return obj.can_execute()


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications."""
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message',
            'action_url', 'action_label', 'is_read', 'read_at',
            'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
