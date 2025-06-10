"""
Celery tasks for automation processing.
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_automation_rules(self):
    """
    Process all active automation rules to check if they should be triggered.
    This task runs periodically to evaluate rule conditions.
    """
    from automation.models import AutomationRule, AutomationLog
    from tenants.models import Tenant
    
    processed_count = 0
    triggered_count = 0
    error_count = 0
    
    try:
        # Get all active rules that could potentially be triggered
        rules = AutomationRule.objects.filter(
            is_enabled=True,
            status='active'
        ).select_related('tenant')
        
        for rule in rules:
            try:
                with transaction.atomic():
                    # Check if rule should be triggered
                    if rule.should_trigger():
                        success = rule.execute()
                        triggered_count += 1
                        
                        if success:
                            logger.info(f"Successfully executed automation rule: {rule.name}")
                        else:
                            logger.warning(f"Automation rule executed with errors: {rule.name}")
                    
                    processed_count += 1
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing automation rule {rule.name}: {str(e)}")
                
                # Log the error
                AutomationLog.objects.create(
                    rule=rule,
                    status='error',
                    message=f'Error during rule evaluation: {str(e)}'
                )
        
        logger.info(
            f"Automation processing completed. "
            f"Processed: {processed_count}, Triggered: {triggered_count}, Errors: {error_count}"
        )
        
        return {
            'processed': processed_count,
            'triggered': triggered_count,
            'errors': error_count
        }
        
    except Exception as e:
        logger.error(f"Critical error in automation processing: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True)
def process_scheduled_rules(self):
    """
    Process time-based automation rules that are scheduled to run.
    """
    from automation.models import AutomationSchedule
    
    now = timezone.now()
    scheduled_rules = AutomationSchedule.objects.filter(
        is_active=True,
        next_run__lte=now,
        rule__is_enabled=True,
        rule__status='active'
    ).select_related('rule')
    
    executed_count = 0
    
    for schedule in scheduled_rules:
        try:
            with transaction.atomic():
                rule = schedule.rule
                
                # Execute the rule
                success = rule.execute()
                executed_count += 1
                
                # Update schedule
                schedule.last_run = now
                schedule.calculate_next_run()
                schedule.save()
                
                logger.info(f"Executed scheduled rule: {rule.name}")
                
        except Exception as e:
            logger.error(f"Error executing scheduled rule {schedule.rule.name}: {str(e)}")
    
    return {'executed': executed_count}


@shared_task
def update_calculated_kpis():
    """
    Update KPIs that are calculated from other KPIs.
    """
    from kpis.models import SmartKPI, KPIDataPoint
    
    # Get all calculated KPIs
    calculated_kpis = SmartKPI.objects.filter(
        data_source_type='calculated',
        is_active=True
    ).prefetch_related('parent_kpis')
    
    updated_count = 0
    today = timezone.now().date()
    
    for kpi in calculated_kpis:
        try:
            # Calculate new value
            new_value = kpi.calculate_value()
            
            if new_value is not None:
                # Check if data point already exists for today
                data_point, created = KPIDataPoint.objects.get_or_create(
                    kpi=kpi,
                    date=today,
                    defaults={
                        'value': new_value,
                        'source': 'calculated',
                        'notes': 'Auto-calculated by system'
                    }
                )
                
                if not created:
                    # Update existing data point
                    data_point.value = new_value
                    data_point.save()
                
                updated_count += 1
                logger.info(f"Updated calculated KPI: {kpi.name} = {new_value}")
                
        except Exception as e:
            logger.error(f"Error calculating KPI {kpi.name}: {str(e)}")
    
    return {'updated': updated_count}


@shared_task
def check_kpi_thresholds():
    """
    Check KPI thresholds and create alerts for breaches.
    """
    from kpis.models import SmartKPI, KPIAlert
    from core.utils import create_notification
    
    alerts_created = 0
    
    # Get all active KPIs with thresholds
    kpis = SmartKPI.objects.filter(
        is_active=True
    ).filter(
        models.Q(critical_threshold__isnull=False) |
        models.Q(warning_threshold__isnull=False) |
        models.Q(target_value__isnull=False)
    ).prefetch_related('stakeholders')
    
    for kpi in kpis:
        try:
            current_value = kpi.get_latest_value()
            
            if current_value is None:
                continue
            
            # Check for threshold breaches
            alerts_to_create = []
            
            # Critical threshold
            if kpi.critical_threshold:
                if ((kpi.trend_direction == 'up_good' and current_value < kpi.critical_threshold) or
                    (kpi.trend_direction == 'down_good' and current_value > kpi.critical_threshold)):
                    
                    # Check if alert already exists
                    existing_alert = KPIAlert.objects.filter(
                        kpi=kpi,
                        alert_type='threshold_breach',
                        severity='critical',
                        is_resolved=False
                    ).first()
                    
                    if not existing_alert:
                        alerts_to_create.append({
                            'alert_type': 'threshold_breach',
                            'severity': 'critical',
                            'title': f'{kpi.name} critical threshold breach',
                            'message': f'Current value ({current_value}) breached critical threshold ({kpi.critical_threshold})',
                            'trigger_value': current_value,
                            'threshold_value': kpi.critical_threshold
                        })
            
            # Warning threshold
            if kpi.warning_threshold and not alerts_to_create:  # Only if no critical alert
                if ((kpi.trend_direction == 'up_good' and current_value < kpi.warning_threshold) or
                    (kpi.trend_direction == 'down_good' and current_value > kpi.warning_threshold)):
                    
                    existing_alert = KPIAlert.objects.filter(
                        kpi=kpi,
                        alert_type='threshold_breach',
                        severity='warning',
                        is_resolved=False
                    ).first()
                    
                    if not existing_alert:
                        alerts_to_create.append({
                            'alert_type': 'threshold_breach',
                            'severity': 'warning',
                            'title': f'{kpi.name} warning threshold breach',
                            'message': f'Current value ({current_value}) breached warning threshold ({kpi.warning_threshold})',
                            'trigger_value': current_value,
                            'threshold_value': kpi.warning_threshold
                        })
            
            # Create alerts and notify stakeholders
            for alert_data in alerts_to_create:
                alert = KPIAlert.objects.create(kpi=kpi, **alert_data)
                alerts_created += 1
                
                # Notify stakeholders
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
                
                logger.info(f"Created KPI alert: {alert.title}")
                
        except Exception as e:
            logger.error(f"Error checking thresholds for KPI {kpi.name}: {str(e)}")
    
    return {'alerts_created': alerts_created}


@shared_task
def cleanup_old_logs():
    """
    Clean up old automation logs and audit logs to prevent database bloat.
    """
    from automation.models import AutomationLog
    from core.models import AuditLog
    
    # Delete automation logs older than 90 days
    cutoff_date = timezone.now() - timedelta(days=90)
    
    automation_deleted = AutomationLog.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]
    
    # Delete audit logs older than 6 months
    audit_cutoff = timezone.now() - timedelta(days=180)
    audit_deleted = AuditLog.objects.filter(
        created_at__lt=audit_cutoff
    ).delete()[0]
    
    logger.info(f"Cleanup completed. Deleted {automation_deleted} automation logs, {audit_deleted} audit logs")
    
    return {
        'automation_logs_deleted': automation_deleted,
        'audit_logs_deleted': audit_deleted
    }


@shared_task
def send_daily_digest():
    """
    Send daily digest emails to users with their relevant updates.
    """
    from django.contrib.auth.models import User
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    from tenants.models import TenantUser
    
    sent_count = 0
    
    # Get all active users who want email notifications
    users = User.objects.filter(
        profile__email_notifications=True,
        is_active=True
    ).select_related('profile')
    
    for user in users:
        try:
            # Get user's tenant(s)
            tenant_users = TenantUser.objects.filter(user=user, is_active=True)
            
            for tenant_user in tenant_users:
                tenant = tenant_user.tenant
                
                # Gather digest data
                digest_data = {
                    'user': user,
                    'tenant': tenant,
                    'date': timezone.now().date(),
                }
                
                # Get user's tasks
                from projects.models import Task
                user_tasks = Task.objects.filter(
                    project__tenant=tenant,
                    assigned_to=user,
                    status__in=['todo', 'in_progress']
                )
                
                digest_data['tasks'] = {
                    'total': user_tasks.count(),
                    'overdue': sum(1 for t in user_tasks if t.is_overdue),
                    'due_today': user_tasks.filter(due_date__date=timezone.now().date()).count(),
                }
                
                # Get unread notifications
                unread_notifications = user.notifications.filter(
                    is_read=False,
                    created_at__date=timezone.now().date()
                )
                
                digest_data['notifications'] = {
                    'count': unread_notifications.count(),
                    'recent': unread_notifications[:5]
                }
                
                # Get KPI alerts
                from kpis.models import KPIAlert
                kpi_alerts = KPIAlert.objects.filter(
                    kpi__tenant=tenant,
                    kpi__stakeholders=user,
                    is_resolved=False,
                    created_at__date=timezone.now().date()
                )
                
                digest_data['kpi_alerts'] = {
                    'count': kpi_alerts.count(),
                    'critical': kpi_alerts.filter(severity='critical').count()
                }
                
                # Only send if there's something to report
                if (digest_data['tasks']['total'] > 0 or 
                    digest_data['notifications']['count'] > 0 or 
                    digest_data['kpi_alerts']['count'] > 0):
                    
                    # Render email template
                    subject = f"Daily Digest - {tenant.name}"
                    html_message = render_to_string('emails/daily_digest.html', digest_data)
                    plain_message = render_to_string('emails/daily_digest.txt', digest_data)
                    
                    send_mail(
                        subject=subject,
                        message=plain_message,
                        html_message=html_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=True
                    )
                    
                    sent_count += 1
                    logger.info(f"Sent daily digest to {user.email} for {tenant.name}")
                
        except Exception as e:
            logger.error(f"Error sending daily digest to {user.email}: {str(e)}")
    
    return {'digests_sent': sent_count}


@shared_task
def generate_monthly_reports():
    """
    Generate monthly reports for all tenants.
    """
    from tenants.models import Tenant
    from projects.models import Project
    from kpis.models import SmartKPI
    from django.db.models import Count, Avg
    
    reports_generated = 0
    current_month = timezone.now().replace(day=1).date()
    
    for tenant in Tenant.objects.filter(status='active'):
        try:
            # Generate project report
            projects = Project.objects.filter(tenant=tenant)
            project_stats = {
                'total': projects.count(),
                'completed_this_month': projects.filter(
                    status='completed',
                    actual_end_date__gte=current_month
                ).count(),
                'average_progress': projects.aggregate(
                    avg_progress=Avg('progress_percentage')
                )['avg_progress'] or 0,
            }
            
            # Generate KPI report
            kpis = SmartKPI.objects.filter(tenant=tenant, is_active=True)
            kpi_stats = {
                'total': kpis.count(),
                'on_target': sum(1 for kpi in kpis if kpi.calculate_performance_status() in ['excellent', 'good']),
                'alerts_this_month': tenant.kpialert_set.filter(
                    created_at__gte=current_month,
                    is_resolved=False
                ).count(),
            }
            
            # Store report data (you might want to create a Report model)
            report_data = {
                'tenant': tenant.name,
                'month': current_month,
                'projects': project_stats,
                'kpis': kpi_stats,
                'generated_at': timezone.now()
            }
            
            # Here you would save the report or send it via email
            logger.info(f"Generated monthly report for {tenant.name}")
            reports_generated += 1
            
        except Exception as e:
            logger.error(f"Error generating monthly report for {tenant.name}: {str(e)}")
    
    return {'reports_generated': reports_generated}
