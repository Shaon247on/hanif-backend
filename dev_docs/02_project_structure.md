# Project Structure

## High-Level Overview

```
django-template/
├── apps/                       # All Django apps
│   ├── common/                 # Shared abstract models, enums, auth backends
│   ├── core/                   # Framework-level utilities
│   ├── user/                   # Authentication & user management
│   └── contact/                # CMS: Terms, Policy, FAQ, Contact
├── config/                     # Project configuration
│   ├── settings/               # Split settings (base/dev/staging/prod)
│   ├── celery.py               # Celery app
│   ├── env.py                  # Environment variable loader
│   ├── urls.py                 # Root URL routing
│   ├── wsgi.py                 # WSGI entry point
│   └── asgi.py                 # ASGI entry point
├── docs/                       # Developer documentation
├── scripts/                    # Ops scripts (entrypoint, db wait)
├── requirements/               # Split requirements
├── manage.py
├── Makefile
├── pyproject.toml
└── Dockerfile
```

## Layer Architecture

```
Request → URL Router → View (thin) → Service (business logic) → Model/ORM → Database
                         ↓
                    Serializer (validation only)
                         ↓
                    Response (standard envelope)
```

## App Details

### `apps/common/` — Shared Foundations
- **`models.py`**: `BaseModel` — every model inherits this (status, created_at, updated_at)
- **`enums.py`**: Global enums like `Status` (ACTIVE, INACTIVE, DRAFT, DELETED)
- **`backends.py`**: Email authentication backend

### `apps/core/` — Framework Utilities
This is NOT a Django app with models. It provides reusable utilities:
- **`exceptions.py`**: Centralized DRF exception handler
- **`responses.py`**: `success_response()` / `error_response()` helpers
- **`pagination.py`**: Standard pagination classes
- **`permissions.py`**: Reusable permission classes (IsActiveUser, IsAdmin, etc.)
- **`throttles.py`**: Rate limiting classes
- **`serializers.py`**: Base serializers, field mixins (Base64ImageField, etc.)
- **`views.py`**: View mixins (QueryParamsMixin)
- **`test_utils.py`**: Base test case with helpers

### `apps/user/` — Authentication
- **`models.py`**: Custom User (UUID, email-based) + PasswordResetOTP
- **`managers.py`**: Custom UserManager
- **`serializers.py`**: Validation-only serializers
- **`services.py`**: All auth business logic (register, verify, reset, etc.)
- **`tasks.py`**: Celery tasks for async email sending
- **`views.py`**: Thin views calling services
- **`tokens.py`**: Email verification token generator

### `apps/contact/` — CMS
- **Models**: Terms, Policy, FAQ, ContactMessage
- **`services.py`**: Admin notification logic
- Fully functional CRUD endpoints

## Rules

1. **Every model** inherits from `BaseModel`
2. **Business logic** goes in `services.py`, never in views or serializers
3. **Serializers** only validate data
4. **Views** only parse requests, call services, and return responses
5. **No file** should exceed ~150 lines
6. **Emails** are sent asynchronously via Celery tasks
