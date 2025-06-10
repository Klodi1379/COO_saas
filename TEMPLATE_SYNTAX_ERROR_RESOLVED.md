# Template Syntax Error Resolution

## Problem
`TemplateSyntaxError: Invalid filter: 'lookup'` at `/kpis/`

## Root Cause
The `search_filters.html` component template was using a custom `lookup` filter but wasn't loading the `coo_extras` template tags where the filter is defined.

## Solutions Applied

### 1. Fixed Template Tags Loading
**File:** `templates/components/search_filters.html`
- ✅ Added `{% load coo_extras %}` at the top of the component template
- ✅ This makes the `lookup` filter available within the component

### 2. Added Missing Filter Configuration
**File:** `kpis/views.py` - `KPIListView.get_context_data()`
- ✅ Added `filter_config` to context with proper filter definitions:
  - Category filter (select dropdown)
  - Data source type filter (select dropdown)  
  - Sort by filter (select dropdown)
- ✅ Each filter includes proper structure with `name`, `label`, `type`, `width`, and `options`

### 3. Added Missing Stats Context
**File:** `kpis/views.py` - `KPIListView.get_context_data()`
- ✅ Added stats for overview cards:
  - `total_kpis`: Total KPI count for tenant
  - `active_kpis`: Active KPI count for tenant
  - `critical_alerts`: Unresolved critical alerts count
  - `total_categories`: Total category count

## Technical Details

### The `lookup` Filter
The `lookup` filter is already defined in `core/templatetags/coo_extras.py`:
```python
@register.filter
def lookup(dictionary, key):
    """Look up a key in a dictionary"""
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None
```

### Filter Configuration Structure
```python
filter_config = [
    {
        'name': 'category',
        'label': 'Category', 
        'type': 'select',
        'width': '3',
        'options': [{'value': cat.id, 'label': cat.name} for cat in categories]
    },
    # ... more filters
]
```

## Status
🎉 **RESOLVED** - The `/kpis/` URL should now work without template syntax errors.

## Files Modified
1. `templates/components/search_filters.html` - Added template tags loading
2. `kpis/views.py` - Added filter configuration and stats to context

## Testing
Visit `http://127.0.0.1:49000/kpis/` to verify:
- ✅ Page loads without template errors
- ✅ Search and filter functionality works
- ✅ Overview stats cards display properly
- ✅ Filter dropdowns populate with correct options
