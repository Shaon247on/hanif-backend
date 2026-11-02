"""
Staging settings.

Usage:
    DJANGO_SETTINGS_MODULE=config.settings.staging
"""

from config import env as env_module
from config.settings.base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = env_module.ALLOWED_HOSTS

# ---------------------------------------------------------------------------
# Database — PostgreSQL required in staging
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env_module.env.db("DATABASE_URL"),
}

# ---------------------------------------------------------------------------
# Security — moderate hardening
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
