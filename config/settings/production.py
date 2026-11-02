"""
Production settings.

Usage:
    DJANGO_SETTINGS_MODULE=config.settings.production
"""

from config import env as env_module
from config.settings.base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = env_module.ALLOWED_HOSTS
if "*" in ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS must not contain '*' in production.")

# ---------------------------------------------------------------------------
# Database — PostgreSQL required
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env_module.env.db("DATABASE_URL"),
}

# ---------------------------------------------------------------------------
# Security hardening
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------------------------------------------------------------------
# Swagger / Admin — disabled by default in production
# ---------------------------------------------------------------------------
DISABLE_SWAGGER = env_module.DISABLE_SWAGGER or True
DISABLE_ADMIN = env_module.DISABLE_ADMIN

# ---------------------------------------------------------------------------
# Sentry (if configured)
# ---------------------------------------------------------------------------
if env_module.SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=env_module.SENTRY_DSN,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Logging — JSON format for production log aggregation
# ---------------------------------------------------------------------------
LOGGING["formatters"]["json"] = {  # noqa: F405
    "()": "django.utils.log.ServerFormatter",
    "format": "[{asctime}] {levelname} {name} {message}",
    "style": "{",
}
