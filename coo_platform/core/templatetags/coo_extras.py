"""
Template utilities and filters for COO Platform
Usage: {% load coo_extras %}
"""

from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse
from urllib.parse import urlencode
import json

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """Look up a key in a dictionary"""
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None

@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Divide value by arg"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
@register.simple_tag
def filter_url_without(get_params, key_to_remove):
    """Remove a key from GET parameters and return URL query string"""
    params = get_params.copy()
    if key_to_remove in params:
        del params[key_to_remove]
    return urlencode(params)

@register.simple_tag
def active_class(request, pattern_or_urlname):
    """Return 'active' class if current URL matches pattern or URL name"""
    try:
        url = reverse(pattern_or_urlname)
        if request.path == url:
            return 'active'
    except:
        if pattern_or_urlname in request.path:
            return 'active'
    return ''

@register.simple_tag
def widget_config(widget, key, default=None):
    """Get configuration value from widget config JSON"""
    try:
        config = json.loads(widget.config) if isinstance(widget.config, str) else widget.config
        return config.get(key, default)
    except:
        return default

@register.inclusion_tag('components/pagination.html')
def render_pagination(page_obj, extra_params=None):
    """Render pagination component"""
    return {
        'page_obj': page_obj,
        'extra_params': extra_params
    }

@register.inclusion_tag('components/stats_card.html')
def stats_card(title, value, icon=None, color='primary', subtitle=None, 
               change_value=None, change_positive=None, change_unit='%', change_period=None):
    """Render stats card component"""
    return {
        'title': title,
        'value': value,
        'icon': icon,
        'color': color,
        'subtitle': subtitle,
        'change_value': change_value,
        'change_positive': change_positive,
        'change_unit': change_unit,
        'change_period': change_period
    }

@register.inclusion_tag('components/loading.html')
def loading_spinner(message=None, size='medium', type='spinner', full_height=False):
    """Render loading component"""
    return {
        'message': message,
        'size': size,
        'type': type,
        'full_height': full_height
    }

@register.filter
def json_script_safe(value):
    """Safely convert Python object to JSON for use in templates"""
    return mark_safe(json.dumps(value))

@register.simple_tag
def performance_status_color(status):
    """Get Bootstrap color class for performance status"""
    colors = {
        'excellent': 'success',
        'good': 'primary', 
        'warning': 'warning',
        'critical': 'danger',
        'unknown': 'secondary'
    }
    return colors.get(status, 'secondary')

@register.simple_tag
def priority_color(priority):
    """Get Bootstrap color class for priority level"""
    colors = {
        'low': 'success',
        'medium': 'warning',
        'high': 'danger',
        'urgent': 'danger'
    }
    return colors.get(priority, 'secondary')

@register.filter
def file_size(bytes):
    """Convert bytes to human readable format"""
    try:
        bytes = float(bytes)
    except (TypeError, ValueError):
        return "0 bytes"
    
    for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} PB"

@register.simple_tag(takes_context=True)
def tenant_url(context, url_name, *args, **kwargs):
    """Generate URL with tenant context"""
    request = context['request']
    url = reverse(url_name, args=args, kwargs=kwargs)
    if hasattr(request, 'tenant') and request.tenant:
        # Add tenant-specific logic if needed
        pass
    return url