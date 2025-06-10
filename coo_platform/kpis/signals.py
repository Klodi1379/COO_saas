"""
Django signals for KPIs app.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import SmartKPI, KPIDataPoint, KPIAlert
from core.utils import create_notification


@receiver(post_save, sender=KPIDataPoint)
def check_kpi_thresholds(sender, instance, created, **kwargs):
    """
    Check for threshold breaches when a new data point is added.
    """
    if not created:
        return
    
    kpi = instance.kpi
    value = instance.value
    
    # Check if we need to create alerts
    alerts_to_create = []
    
    # Critical threshold check
    if kpi.critical_threshold:
        if kpi.trend_direction == 'up_good' and value < kpi.critical_threshold:
            alerts_to_create.append({
                'alert_type': 'threshold_breach',
                'severity': 'critical',
                'title': f'{kpi.name} below critical threshold',
                'message': f'Current value ({value}) is below the critical threshold ({kpi.critical_threshold})',
                'trigger_value': value,
                'threshold_value': kpi.critical_threshold
            })
        elif kpi.trend_direction == 'down_good' and value > kpi.critical_threshold:
            alerts_to_create.append({
                'alert_type': 'threshold_breach',
                'severity': 'critical',
                'title': f'{kpi.name} above critical threshold',
                'message': f'Current value ({value}) is above the critical threshold ({kpi.critical_threshold})',
                'trigger_value': value,
                'threshold_value': kpi.critical_threshold
            })
    
    # Warning threshold check
    if kpi.warning_threshold:
        if kpi.trend_direction == 'up_good' and value < kpi.warning_threshold:
            # Only create if not already critical
            if not any(alert['severity'] == 'critical' for alert in alerts_to_create):
                alerts_to_create.append({
                    'alert_type': 'threshold_breach',
                    'severity': 'warning',
                    'title': f'{kpi.name} below warning threshold',
                    'message': f'Current value ({value}) is below the warning threshold ({kpi.warning_threshold})',
                    'trigger_value': value,
                    'threshold_value': kpi.warning_threshold
                })
        elif kpi.trend_direction == 'down_good' and value > kpi.warning_threshold:
            if not any(alert['severity'] == 'critical' for alert in alerts_to_create):
                alerts_to_create.append({
                    'alert_type': 'threshold_breach',
                    'severity': 'warning',
                    'title': f'{kpi.name} above warning threshold',
                    'message': f'Current value ({value}) is above the warning threshold ({kpi.warning_threshold})',
                    'trigger_value': value,
                    'threshold_value': kpi.warning_threshold
                })
    
    # Target achievement check
    if kpi.target_value:
        if kpi.trend_direction == 'up_good' and value >= kpi.target_value:
            # Check if this is the first time hitting target
            previous_datapoints = kpi.datapoints.filter(
                date__lt=instance.date
            ).order_by('-date')[:5]
            
            if not any(dp.value >= kpi.target_value for dp in previous_datapoints):
                alerts_to_create.append({
                    'alert_type': 'target_achieved',
                    'severity': 'info',
                    'title': f'{kpi.name} target achieved!',
                    'message': f'Congratulations! The target value of {kpi.target_value} has been achieved with a current value of {value}',
                    'trigger_value': value,
                    'threshold_value': kpi.target_value
                })
        elif kpi.trend_direction == 'down_good' and value <= kpi.target_value:
            previous_datapoints = kpi.datapoints.filter(
                date__lt=instance.date
            ).order_by('-date')[:5]
            
            if not any(dp.value <= kpi.target_value for dp in previous_datapoints):
                alerts_to_create.append({
                    'alert_type': 'target_achieved',
                    'severity': 'info',
                    'title': f'{kpi.name} target achieved!',
                    'message': f'Congratulations! The target value of {kpi.target_value} has been achieved with a current value of {value}',
                    'trigger_value': value,
                    'threshold_value': kpi.target_value
                })
    
    # Create alerts
    for alert_data in alerts_to_create:
        # Check if similar alert already exists and is not resolved
        existing_alert = KPIAlert.objects.filter(
            kpi=kpi,
            alert_type=alert_data['alert_type'],
            severity=alert_data['severity'],
            is_resolved=False
        ).first()
        
        if not existing_alert:
            alert = KPIAlert.objects.create(
                kpi=kpi,
                **alert_data
            )
            
            # Send notifications to stakeholders
            stakeholders = list(kpi.stakeholders.all())
            if kpi.owner and kpi.owner not in stakeholders:
                stakeholders.append(kpi.owner)
            
            for stakeholder in stakeholders:
                create_notification(
                    recipient=stakeholder,
                    notification_type='kpi_alert',
                    title=alert.title,
                    message=alert.message,
                    action_url=kpi.get_absolute_url(),
                    action_label='View KPI'
                )


@receiver(post_save, sender=SmartKPI)
def schedule_kpi_updates(sender, instance, created, **kwargs):
    """
    Schedule automatic updates for KPIs.
    """
    if created or 'auto_update_frequency' in getattr(instance, '_updated_fields', set()):
        if instance.auto_update_frequency:
            instance.schedule_next_update()


@receiver(post_save, sender=KPIDataPoint)
def auto_resolve_alerts(sender, instance, created, **kwargs):
    """
    Auto-resolve alerts when KPI values return to normal ranges.
    """
    if not created:
        return
    
    kpi = instance.kpi
    value = instance.value
    
    # Find alerts that might be resolved
    unresolved_alerts = KPIAlert.objects.filter(
        kpi=kpi,
        is_resolved=False,
        alert_type='threshold_breach'
    )
    
    for alert in unresolved_alerts:
        should_resolve = False
        
        if alert.severity == 'critical' and kpi.critical_threshold:
            if kpi.trend_direction == 'up_good' and value >= kpi.critical_threshold:
                should_resolve = True
            elif kpi.trend_direction == 'down_good' and value <= kpi.critical_threshold:
                should_resolve = True
        
        elif alert.severity == 'warning' and kpi.warning_threshold:
            if kpi.trend_direction == 'up_good' and value >= kpi.warning_threshold:
                should_resolve = True
            elif kpi.trend_direction == 'down_good' and value <= kpi.warning_threshold:
                should_resolve = True
        
        if should_resolve:
            alert.resolve()
            
            # Notify stakeholders that the issue is resolved
            stakeholders = list(kpi.stakeholders.all())
            if kpi.owner and kpi.owner not in stakeholders:
                stakeholders.append(kpi.owner)
            
            for stakeholder in stakeholders:
                create_notification(
                    recipient=stakeholder,
                    notification_type='info',
                    title=f'{kpi.name} alert resolved',
                    message=f'The alert "{alert.title}" has been automatically resolved. Current value: {value}',
                    action_url=kpi.get_absolute_url(),
                    action_label='View KPI'
                )


@receiver(post_save, sender=KPIDataPoint)
def update_calculated_kpis(sender, instance, created, **kwargs):
    """
    Update dependent KPIs when a data point is added.
    """
    if not created:
        return
    
    kpi = instance.kpi
    
    # Find KPIs that depend on this one
    dependent_kpis = SmartKPI.objects.filter(
        parent_kpis=kpi,
        data_source_type='calculated',
        is_active=True
    )
    
    for dependent_kpi in dependent_kpis:
        # Calculate new value
        new_value = dependent_kpi.calculate_value()
        
        if new_value is not None:
            # Create new data point for calculated KPI
            KPIDataPoint.objects.create(
                kpi=dependent_kpi,
                date=instance.date,
                value=new_value,
                source='calculated',
                notes=f'Auto-calculated from {kpi.name}'
            )


@receiver(post_save, sender=SmartKPI)
def create_initial_dashboard_entry(sender, instance, created, **kwargs):
    """
    Add featured KPIs to user's default dashboard.
    """
    if created and instance.is_featured:
        from .models import KPIDashboard, DashboardKPI
        
        # Find or create owner's default dashboard
        if instance.owner:
            dashboard, created = KPIDashboard.objects.get_or_create(
                tenant=instance.tenant,
                owner=instance.owner,
                name='My Dashboard',
                defaults={
                    'description': 'Personal KPI dashboard',
                    'layout': {'columns': 12, 'row_height': 150}
                }
            )
            
            # Add KPI to dashboard if not already there
            if not DashboardKPI.objects.filter(dashboard=dashboard, kpi=instance).exists():
                # Find next available position
                existing_positions = DashboardKPI.objects.filter(
                    dashboard=dashboard
                ).values_list('position_x', 'position_y')
                
                # Simple positioning logic - place in next available 4-wide slot
                position_x = 0
                position_y = 0
                
                while (position_x, position_y) in existing_positions:
                    position_x += 4
                    if position_x >= 12:
                        position_x = 0
                        position_y += 1
                
                DashboardKPI.objects.create(
                    dashboard=dashboard,
                    kpi=instance,
                    position_x=position_x,
                    position_y=position_y,
                    width=4,
                    height=4
                )


@receiver(post_delete, sender=KPIDataPoint)
def cleanup_related_data(sender, instance, **kwargs):
    """
    Clean up related data when a data point is deleted.
    """
    # Mark related alerts as resolved if they were triggered by this data point
    KPIAlert.objects.filter(
        kpi=instance.kpi,
        trigger_value=instance.value,
        is_resolved=False
    ).update(is_resolved=True, resolved_at=timezone.now())
