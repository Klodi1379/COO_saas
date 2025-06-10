# COO Platform - Your Operating Platform

A comprehensive COO-as-a-Service platform built with Django that helps organizations streamline operations, track KPIs, manage projects, and automate workflows.

## 🚀 Features

### Core Functionality
- **Multi-Tenant Architecture**: Secure tenant isolation for multiple organizations
- **Project Management**: Comprehensive project and task management with team collaboration
- **KPI Tracking**: Real-time KPI monitoring with customizable dashboards and alerts
- **Workflow Automation**: Intelligent automation engine with custom triggers and actions
- **Real-time Dashboards**: Customizable widgets and real-time data updates
- **Team Collaboration**: Role-based permissions and team management

### Advanced Features
- **Smart KPIs**: Automated data collection and calculated metrics
- **Predictive Analytics**: Trend analysis and performance predictions
- **API Integration**: RESTful API for external integrations
- **Automation Rules**: Complex workflow automation with multiple triggers
- **Custom Branding**: White-label options for enterprise clients
- **Audit Trail**: Comprehensive logging and activity tracking

## 🛠️ Technology Stack

- **Backend**: Django 4.2+, Django REST Framework
- **Database**: PostgreSQL (with SQLite fallback for development)
- **Cache/Queue**: Redis, Celery
- **Frontend**: Bootstrap 5, Chart.js, Alpine.js
- **Real-time**: Django Channels, WebSockets
- **Authentication**: Django Allauth
- **File Storage**: Django Storages (S3 compatible)

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL 12+ (optional, SQLite works for development)
- Redis 6+ (for caching and task queue)
- Node.js 16+ (for frontend build tools, optional)

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd COO_saas

# Run the setup script (Windows)
setup_env.bat

# Or manually create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```env
# Django Configuration
SECRET_KEY=your-secret-key-here
DEBUG=True
USE_SQLITE=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration (PostgreSQL - optional)
# USE_SQLITE=False
# DB_NAME=coo_platform
# DB_USER=postgres
# DB_PASSWORD=your_password
# DB_HOST=localhost
# DB_PORT=5432

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=noreply@cooplatform.com
```

### 3. Database Setup

```bash
# Navigate to the Django project directory
cd coo_platform

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load demo data (optional)
python manage.py setup_demo_data --admin-email=admin@demo.com
```

### 4. Run the Development Server

```bash
# Start the Django development server
python manage.py runserver

# In another terminal, start Celery worker (optional)
celery -A coo_platform worker -l info

# In another terminal, start Celery beat scheduler (optional)
celery -A coo_platform beat -l info
```

### 5. Access the Platform

- **Main Application**: http://localhost:8000/
- **Admin Interface**: http://localhost:8000/admin/
- **API Documentation**: http://localhost:8000/api/v1/
- **Dashboard**: http://localhost:8000/dashboard/

## 📁 Project Structure

```
COO_saas/
├── coo_platform/                 # Main Django project
│   ├── coo_platform/            # Project settings
│   ├── core/                    # Core functionality
│   ├── tenants/                 # Multi-tenant management
│   ├── projects/                # Project management
│   ├── kpis/                    # KPI tracking
│   ├── automation/              # Workflow automation
│   ├── dashboard/               # Dashboard interface
│   ├── api/                     # REST API
│   ├── templates/               # HTML templates
│   └── static/                  # Static files
├── requirements.txt             # Python dependencies
├── setup_env.bat               # Environment setup script
└── README.md                   # This file
```

## 🔧 Configuration

### Multi-Tenant Setup

The platform supports multiple organizations (tenants) with complete data isolation:

```python
# In your views, always filter by current tenant
from tenants.middleware import get_current_tenant

def my_view(request):
    tenant = get_current_tenant()
    projects = Project.objects.filter(tenant=tenant)
```

### Custom Settings

Customize platform behavior in `settings.py`:

```python
COO_PLATFORM_SETTINGS = {
    'DEFAULT_SUBSCRIPTION_TIER': 'basic',
    'MAX_PROJECTS_PER_TIER': {
        'basic': 5,
        'professional': 25,
        'enterprise': 100,
    },
    'FEATURES_PER_TIER': {
        'basic': ['projects', 'tasks', 'basic_kpis'],
        'professional': ['projects', 'tasks', 'advanced_kpis', 'automation'],
        'enterprise': ['all_features', 'custom_branding', 'api_access'],
    }
}
```

## 📊 Usage Examples

### Creating a KPI

```python
from kpis.models import SmartKPI, KPICategory

# Create a KPI category
category = KPICategory.objects.create(
    tenant=tenant,
    name="Financial",
    category_type="financial"
)

# Create a KPI
kpi = SmartKPI.objects.create(
    tenant=tenant,
    name="Monthly Revenue",
    category=category,
    unit="$",
    target_value=50000,
    warning_threshold=45000,
    critical_threshold=40000,
    trend_direction="up_good"
)
```

### Setting up Automation

```python
from automation.models import AutomationRule, AutomationAction

# Create an automation rule
rule = AutomationRule.objects.create(
    tenant=tenant,
    name="Low Revenue Alert",
    trigger_type="kpi_threshold",
    trigger_config={
        "kpi_id": kpi.id,
        "operator": "lt",
        "threshold": 45000
    },
    status="active"
)

# Add an action
action = AutomationAction.objects.create(
    rule=rule,
    name="Send Email Alert",
    action_type="send_email",
    action_config={
        "recipients": ["admin@company.com"],
        "subject": "Revenue Alert",
        "message": "Revenue has dropped below threshold"
    }
)
```

### API Usage

```python
# Get project list via API
import requests

response = requests.get(
    "http://localhost:8000/api/v1/projects/",
    headers={"Authorization": "Token your-api-token"}
)
projects = response.json()
```

## 🔐 Security Features

- **Multi-tenant data isolation**
- **Role-based access control**
- **CSRF protection**
- **SQL injection prevention**
- **XSS protection**
- **Secure session management**
- **API authentication**
- **Audit logging**

## 🚀 Deployment

### Production Checklist

1. **Environment Variables**:
   ```env
   DEBUG=False
   SECRET_KEY=your-production-secret-key
   USE_SQLITE=False
   DB_NAME=your_production_db
   ALLOWED_HOSTS=your-domain.com
   ```

2. **Database**:
   - Set up PostgreSQL
   - Run migrations
   - Create superuser

3. **Static Files**:
   ```bash
   python manage.py collectstatic
   ```

4. **Web Server**:
   - Configure nginx/Apache
   - Set up SSL certificates
   - Configure WSGI server (Gunicorn)

5. **Background Tasks**:
   - Set up Celery workers
   - Configure Redis
   - Set up monitoring

### Docker Deployment

```dockerfile
# Dockerfile example
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["gunicorn", "coo_platform.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## 📈 Monitoring and Analytics

### Built-in Analytics

- **Project performance metrics**
- **KPI trend analysis**
- **Team productivity reports**
- **System usage statistics**
- **Automation execution logs**

### Custom Dashboards

Create custom widgets and dashboards:

```python
from dashboard.models import DashboardWidget

widget = DashboardWidget.objects.create(
    tenant=tenant,
    title="Revenue Trend",
    widget_type="kpi_chart",
    config={
        "kpi_id": revenue_kpi.id,
        "chart_type": "line",
        "days": 30
    }
)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Development Guidelines

- Follow PEP 8 style guide
- Write comprehensive tests
- Update documentation
- Use meaningful commit messages

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: Check the `/docs` directory
- **Issues**: Create a GitHub issue
- **Discussions**: Use GitHub Discussions
- **Email**: support@cooplatform.com

## 🗺️ Roadmap

### Upcoming Features

- [ ] Advanced reporting engine
- [ ] Mobile application
- [ ] Integration marketplace
- [ ] Machine learning insights
- [ ] Advanced workflow designer
- [ ] Multi-language support

### Version History

- **v1.0.0**: Initial release with core features
- **v1.1.0**: Advanced automation and API improvements
- **v1.2.0**: Enhanced dashboard and analytics

## 🙏 Acknowledgments

- Django and Django REST Framework communities
- Bootstrap and Chart.js teams
- All contributors and users

---

**COO Platform** - Empowering organizations with operational excellence through technology.
