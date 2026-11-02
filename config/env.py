"""
Environment variable loader.

All environment variables must be accessed through this module.
Never use os.getenv() directly in settings or app code.
"""

import os

import environ

# Load .env file from project root
env = environ.Env()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"), overwrite=False)


# ---------------------------------------------------------------------------
# Core Django
# ---------------------------------------------------------------------------
DEBUG = env.bool("DEBUG", default=False)
SECRET_KEY = env.str("SECRET_KEY", default="CHANGE-ME-IN-PRODUCTION")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_URL = env.str("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3")

# ---------------------------------------------------------------------------
# CORS / CSRF
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_HOST = env.str("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default="")
EMAIL_VERIFICATION_TIMEOUT = env.int("EMAIL_VERIFICATION_TIMEOUT", default=86400)

# ---------------------------------------------------------------------------
# Project metadata (for Swagger / docs)
# ---------------------------------------------------------------------------
PROJECT_NAME = env.str("PROJECT_NAME", default="Django Project")
PROJECT_DESCRIPTION = env.str("PROJECT_DESCRIPTION", default="Django REST API")
PROJECT_VERSION = env.str("PROJECT_VERSION", default="v1")
SWAGGER_DEFAULT_API_URL = env.str("SWAGGER_DEFAULT_API_URL", default="http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
DISABLE_SWAGGER = env.bool("DISABLE_SWAGGER", default=False)
DISABLE_ADMIN = env.bool("DISABLE_ADMIN", default=False)

# ---------------------------------------------------------------------------
# Redis / Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default="redis://localhost:6379/0")
REDIS_URL = env.str("REDIS_URL", default="redis://localhost:6379/1")

# ---------------------------------------------------------------------------
# Allowed hosts
# ---------------------------------------------------------------------------
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# ---------------------------------------------------------------------------
# Admin notification email (for contact form, etc.)
# ---------------------------------------------------------------------------
ADMIN_NOTIFICATION_EMAIL = env.str("ADMIN_NOTIFICATION_EMAIL", default="")

# ---------------------------------------------------------------------------
# Payment webhooks
# ---------------------------------------------------------------------------
STRIPE_WEBHOOK_SECRET = env.str("STRIPE_WEBHOOK_SECRET", default="")
REVENUECAT_WEBHOOK_SECRET = env.str("REVENUECAT_WEBHOOK_SECRET", default="")

# ---------------------------------------------------------------------------
# Sentry (optional)
# ---------------------------------------------------------------------------
SENTRY_DSN = env.str("SENTRY_DSN", default="")
