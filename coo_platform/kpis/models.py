"""
KPI models for comprehensive performance tracking.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from django.db.models import Avg, Sum, Count, Max, Min
from core.models import TimeStampedModel, UUIDModel
from tenants.models import TenantAwareModel
from decimal import Decimal
import json
from datetime import datetime, timedelta


class KPICategory(TenantAwareModel, TimeStampedModel):
    """
    Categories for organizing KPIs (Financial, Operational, Customer, etc.).
    """
    CATEGORY_TYPES = [
        ('financial', 'Financial'),
        ('operational', 'Operational'),
        ('customer', 'Customer'),
        ('growth', 'Growth'),
        ('team', 'Team Performance'),
        ('quality', 'Quality'),
        ('sustainability', 'Sustainability'),
        ('innovation', 'Innovation'),
    ]
    
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code")
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name_plural = "KPI Categories"
        unique_together = ['tenant', 'name']
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name
    
    @property
    def kpi_count(self):
        return self.kpis.filter(is_active=True).count()


class SmartKPI(UUIDModel, TenantAwareModel, TimeStampedModel):
    """
    Enhanced KPI model with automation and advanced analytics capabilities.
    """
    DATA_SOURCE_TYPES = [
        ('manual', 'Manual Entry'),
        ('api', 'API Integration'),
        ('csv_upload', 'CSV Upload'),
        ('database', 'Database Query'),
        ('calculated', 'Calculated from Other KPIs'),
    ]
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    CALCULATION_METHODS = [
        ('sum', 'Sum'),
        ('average', 'Average'),
        ('count', 'Count'),
        ('percentage', 'Percentage'),
        ('ratio', 'Ratio'),
        ('custom', 'Custom Formula'),
    ]
    
    TREND_DIRECTIONS = [
        ('up_good', 'Higher is Better'),
        ('down_good', 'Lower is Better'),
        ('stable_good', 'Stable is Better'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        KPICategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='kpis'
    )
    
    # Data Source Configuration
    data_source_type = models.CharField(max_length=20, choices=DATA_SOURCE_TYPES, default='manual')
    data_source_config = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Configuration for automated data collection"
    )
    
    # Calculation and Formula
    calculation_method = models.CharField(max_length=20, choices=CALCULATION_METHODS, default='sum')
    calculation_formula = models.TextField(
        blank=True,
        help_text="Custom formula for calculated KPIs (use Python syntax)"
    )
    parent_kpis = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='dependent_kpis',
        help_text="KPIs this one depends on for calculation"
    )
    
    # Units and Formatting
    unit = models.CharField(max_length=20, blank=True, help_text="e.g., '$', '%', 'hours', 'count'")
    decimal_places = models.PositiveIntegerField(default=2)
    
    # Targets and Thresholds
    target_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    warning_threshold = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    critical_threshold = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    trend_direction = models.CharField(max_length=15, choices=TREND_DIRECTIONS, default='up_good')
    
    # Automation Settings
    auto_update_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    last_auto_update = models.DateTimeField(null=True, blank=True)
    next_auto_update = models.DateTimeField(null=True, blank=True)
    
    # Ownership and Responsibility
    owner = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='owned_kpis'
    )
    stakeholders = models.ManyToManyField(
        User,
        blank=True,
        related_name='stakeholder_kpis',
        help_text="Users who should be notified about this KPI"
    )
    
    # Status and Configuration
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Show on main dashboard")
    
    # Display Settings
    chart_type = models.CharField(
        max_length=20,
        choices=[
            ('line', 'Line Chart'),
            ('bar', 'Bar Chart'),
            ('area', 'Area Chart'),
            ('gauge', 'Gauge'),
            ('number', 'Number Display'),
        ],
        default='line'
    )
    
    class Meta:
        verbose_name = "Smart KPI"
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'is_featured']),
            models.Index(fields=['data_source_type', 'next_auto_update']),
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        if self.calculation_method == 'custom' and not self.calculation_formula:
            raise ValidationError('Custom calculation method requires a formula.')
        
        if self.data_source_type == 'calculated' and not self.parent_kpis.exists():
            raise ValidationError('Calculated KPIs must have parent KPIs defined.')
    
    def get_absolute_url(self):
        return reverse('kpis:detail', kwargs={'pk': self.pk})
    
    def get_latest_value(self):
        """Get the most recent data point value."""
        latest = self.datapoints.order_by('-date').first()
        return latest.value if latest else None
    
    def get_trend_data(self, days=30):
        """Get trend data for the specified number of days."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        datapoints = self.datapoints.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        return [
            {
                'date': dp.date.isoformat(),
                'value': float(dp.value),
                'target': float(self.target_value) if self.target_value else None
            }
            for dp in datapoints
        ]
    
    def calculate_performance_status(self):
        """Calculate current performance status based on thresholds."""
        current_value = self.get_latest_value()
        if not current_value or not self.target_value:
            return 'unknown'
        
        # Determine if we're meeting targets based on trend direction
        if self.trend_direction == 'up_good':
            if current_value >= self.target_value:
                return 'excellent'
            elif self.warning_threshold and current_value >= self.warning_threshold:
                return 'good'
            elif self.critical_threshold and current_value >= self.critical_threshold:
                return 'warning'
            else:
                return 'critical'
        
        elif self.trend_direction == 'down_good':
            if current_value <= self.target_value:
                return 'excellent'
            elif self.warning_threshold and current_value <= self.warning_threshold:
                return 'good'
            elif self.critical_threshold and current_value <= self.critical_threshold:
                return 'warning'
            else:
                return 'critical'
        
        else:  # stable_good
            target_variance = abs(current_value - self.target_value)
            if target_variance <= (self.target_value * Decimal('0.05')):  # 5% variance
                return 'excellent'
            elif target_variance <= (self.target_value * Decimal('0.10')):  # 10% variance
                return 'good'
            elif target_variance <= (self.target_value * Decimal('0.20')):  # 20% variance
                return 'warning'
            else:
                return 'critical'
    
    def calculate_value(self):
        """Calculate KPI value based on its configuration."""
        if self.data_source_type != 'calculated':
            return None
        
        if not self.parent_kpis.exists():
            return None
        
        # Get latest values from parent KPIs
        parent_values = {}
        for parent_kpi in self.parent_kpis.all():
            parent_values[f'kpi_{parent_kpi.id}'] = parent_kpi.get_latest_value() or 0
        
        # Execute custom formula if provided
        if self.calculation_method == 'custom' and self.calculation_formula:
            try:
                # Safe evaluation of formula
                allowed_names = {
                    **parent_values,
                    'sum': sum,
                    'max': max,
                    'min': min,
                    'abs': abs,
                    'round': round,
                }
                result = eval(self.calculation_formula, {"__builtins__": {}}, allowed_names)
                return Decimal(str(result))
            except Exception as e:
                print(f"Error calculating KPI {self.name}: {e}")
                return None
        
        # Standard calculation methods
        values = list(parent_values.values())
        if not values:
            return None
        
        if self.calculation_method == 'sum':
            return sum(values)
        elif self.calculation_method == 'average':
            return sum(values) / len(values)
        elif self.calculation_method == 'count':
            return len(values)
        
        return None
    
    def schedule_next_update(self):
        """Schedule the next automatic update."""
        if not self.auto_update_frequency:
            return
        
        now = timezone.now()
        
        if self.auto_update_frequency == 'daily':
            self.next_auto_update = now + timedelta(days=1)
        elif self.auto_update_frequency == 'weekly':
            self.next_auto_update = now + timedelta(weeks=1)
        elif self.auto_update_frequency == 'monthly':
            self.next_auto_update = now + timedelta(days=30)
        elif self.auto_update_frequency == 'quarterly':
            self.next_auto_update = now + timedelta(days=90)
        elif self.auto_update_frequency == 'yearly':
            self.next_auto_update = now + timedelta(days=365)
        
        self.save(update_fields=['next_auto_update'])


class KPIDataPoint(UUIDModel, TimeStampedModel):
    """
    Individual data points for KPIs with rich metadata.
    """
    kpi = models.ForeignKey(SmartKPI, on_delete=models.CASCADE, related_name='datapoints')
    date = models.DateField()
    value = models.DecimalField(max_digits=15, decimal_places=4)
    
    # Data source tracking
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    source = models.CharField(
        max_length=50,
        choices=[
            ('manual', 'Manual Entry'),
            ('api', 'API Import'),
            ('csv', 'CSV Upload'),
            ('calculated', 'Auto-calculated'),
        ],
        default='manual'
    )
    
    # Additional context
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Quality indicators
    is_estimated = models.BooleanField(default=False)
    confidence_level = models.PositiveIntegerField(
        default=100,
        help_text="Confidence in this data point (0-100%)"
    )
    
    class Meta:
        unique_together = ['kpi', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['kpi', 'date']),
            models.Index(fields=['date', 'source']),
        ]
    
    def __str__(self):
        return f"{self.kpi.name} - {self.date}: {self.value}"
    
    @property
    def formatted_value(self):
        """Return formatted value with unit."""
        places = self.kpi.decimal_places
        value = round(float(self.value), places)
        
        if self.kpi.unit == '%':
            return f"{value}%"
        elif self.kpi.unit == '$':
            return f"${value:,.{places}f}"
        elif self.kpi.unit:
            return f"{value} {self.kpi.unit}"
        else:
            return str(value)


class KPIAlert(UUIDModel, TimeStampedModel):
    """
    Alerts triggered when KPIs breach thresholds.
    """
    ALERT_TYPES = [
        ('threshold_breach', 'Threshold Breach'),
        ('trend_warning', 'Trend Warning'),
        ('data_missing', 'Data Missing'),
        ('target_achieved', 'Target Achieved'),
        ('improvement_opportunity', 'Improvement Opportunity'),
    ]
    
    SEVERITY_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    
    kpi = models.ForeignKey(SmartKPI, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Alert trigger data
    trigger_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    threshold_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    
    # Status tracking
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='acknowledged_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    # Auto-resolution
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['kpi', 'is_resolved']),
            models.Index(fields=['severity', 'is_acknowledged']),
        ]
    
    def __str__(self):
        return f"{self.kpi.name} - {self.title}"
    
    def acknowledge(self, user):
        """Acknowledge the alert."""
        if not self.is_acknowledged:
            self.is_acknowledged = True
            self.acknowledged_by = user
            self.acknowledged_at = timezone.now()
            self.save(update_fields=['is_acknowledged', 'acknowledged_by', 'acknowledged_at'])
    
    def resolve(self):
        """Mark alert as resolved."""
        if not self.is_resolved:
            self.is_resolved = True
            self.resolved_at = timezone.now()
            self.save(update_fields=['is_resolved', 'resolved_at'])


class KPIDashboard(UUIDModel, TenantAwareModel, TimeStampedModel):
    """
    Custom dashboards for KPI visualization.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kpi_dashboards')
    
    # Dashboard configuration
    layout = models.JSONField(default=dict, help_text="Dashboard layout configuration")
    kpis = models.ManyToManyField(SmartKPI, through='DashboardKPI')
    
    # Sharing and permissions
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(
        User,
        blank=True,
        related_name='shared_dashboards'
    )
    
    # Display settings
    refresh_interval = models.PositiveIntegerField(
        default=300,
        help_text="Auto-refresh interval in seconds"
    )
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('kpis:dashboard', kwargs={'pk': self.pk})


class DashboardKPI(TimeStampedModel):
    """
    Through model for KPIs on dashboards with positioning.
    """
    dashboard = models.ForeignKey(KPIDashboard, on_delete=models.CASCADE)
    kpi = models.ForeignKey(SmartKPI, on_delete=models.CASCADE)
    
    # Position and size
    position_x = models.PositiveIntegerField(default=0)
    position_y = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=6)  # Grid units
    height = models.PositiveIntegerField(default=4)  # Grid units
    
    # Display overrides
    chart_type_override = models.CharField(max_length=20, blank=True)
    title_override = models.CharField(max_length=200, blank=True)
    
    class Meta:
        unique_together = ['dashboard', 'kpi']
        ordering = ['position_y', 'position_x']
    
    def __str__(self):
        return f"{self.dashboard.name} - {self.kpi.name}"
