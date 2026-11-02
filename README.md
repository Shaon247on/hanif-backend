# Django DRF Template

A production-grade Django REST Framework template for freelance backend projects. Designed for teams where developers come and go — enforcing conventions so anyone can pick up any project.

## Features

- **Django 5.1+** with Django REST Framework 3.15+
- **JWT Authentication** (SimpleJWT) with email-based login
- **Service Layer Architecture** — thin views, fat services
- **Centralized Exception Handling** — consistent JSON error envelopes
- **Split Settings** — development / staging / production
- **Celery + Redis** — async task queue with email sending
- **Docker** — multi-stage production builds
- **API Documentation** — Swagger/OpenAPI via drf-yasg
- **Testing** — pytest with coverage, base test utilities
- **Code Quality** — ruff linting/formatting, pre-commit hooks
- **Rate Limiting** — throttling on auth endpoints
- **Pagination** — standard pagination on all list endpoints

## Quick Start

```bash
# 1. Clone the template
git clone <repository-url> my-project
cd my-project

# 2. Set up virtual environment
make setup
source .venv/bin/activate

# 3. Install dependencies
make install

# 4. Run the server
make run
```

The API is now running at `http://127.0.0.1:8000/`
- **Swagger**: `http://127.0.0.1:8000/swagger/`
- **Admin**: `http://127.0.0.1:8000/admin/`
- **Health**: `http://127.0.0.1:8000/health/`

## Project Structure

```
├── apps/                   # All Django apps
│   ├── common/             # Shared models, enums, auth backends
│   ├── core/               # Framework utilities (pagination, permissions, etc.)
│   ├── user/               # Authentication & user management
│   └── contact/            # CMS: Terms, Policy, FAQ, Contact
├── config/                 # Django project configuration
│   ├── settings/           # Split settings (base/dev/staging/prod)
│   ├── celery.py           # Celery configuration
│   ├── urls.py             # Root URL routing
│   └── env.py              # Environment variable loader
├── docs/                   # Developer documentation
├── scripts/                # Deployment scripts
├── requirements/           # Split requirements (base/dev/prod)
├── Makefile                # Developer commands
└── pyproject.toml          # Tool configuration (ruff, pytest, mypy)
```

## Available Commands

```bash
make help          # Show all available commands
make run           # Start development server
make test          # Run tests with coverage
make lint          # Run linter
make format        # Format code
make migrate       # Run migrations
make superuser     # Create superuser
make docker-up     # Start PostgreSQL + Redis
make celery        # Start Celery worker
```

## Documentation

| Doc | Description |
|-----|-------------|
| [Getting Started](docs/01_getting_started.md) | Full setup guide |
| [Project Structure](docs/02_project_structure.md) | Architecture overview |
| [Creating an App](docs/03_creating_an_app.md) | Step-by-step app creation |
| [API Conventions](docs/04_api_conventions.md) | Response format, errors, pagination |
| [Authentication](docs/05_authentication.md) | JWT auth flow |
| [Naming Conventions](docs/06_naming_conventions.md) | Code style rules |
| [Testing Guide](docs/07_testing_guide.md) | Writing tests |
| [Deployment](docs/08_deployment.md) | Docker & VPS deployment |
| [Generic Views](docs/09_generic_views_guide.md) | DRF views reference |

## Key Architecture Decisions

### Service Layer Pattern
Business logic lives in `services.py`, not in views or serializers:
```
Request → View (parse/validate) → Service (business logic) → Response
```

### Consistent Response Envelope
Every API response follows this format:
```json
{
    "success": true,
    "details": "Operation successful.",
    "code": "SUCCESS",
    "status_code": 200,
    "data": { ... }
}
```

### Environment-Based Settings
```bash
# Development (default)
DJANGO_SETTINGS_MODULE=config.settings.development

# Staging
DJANGO_SETTINGS_MODULE=config.settings.staging

# Production
DJANGO_SETTINGS_MODULE=config.settings.production
```

## License

See the `LICENSE` file for details.
