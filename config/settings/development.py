"""
Development settings.

Usage:
    DJANGO_SETTINGS_MODULE=config.settings.development
"""

from config import env as env_module
from config.settings.base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# ---------------------------------------------------------------------------
# Time zone — local testing happens in Bangladesh; production stays on US Eastern
# ---------------------------------------------------------------------------
TIME_ZONE = env_module.env.str("TIME_ZONE", default="Asia/Dhaka")  # noqa: F405
CELERY_TIMEZONE = TIME_ZONE

# ---------------------------------------------------------------------------
# Database — SQLite by default for easy local dev
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env_module.env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3"),  # noqa: F405
}

# ---------------------------------------------------------------------------
# Email — use SMTP by default, can be overridden to console backend in env
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env_module.env.str("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")

# ---------------------------------------------------------------------------
# Celery — run tasks synchronously in development
# ---------------------------------------------------------------------------
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ---------------------------------------------------------------------------
# CORS — allow all origins in development
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True

# ---------------------------------------------------------------------------
# Django Debug Toolbar (if installed)
# ---------------------------------------------------------------------------
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
    INTERNAL_IPS = ["127.0.0.1"]
except ImportError:
    pass

# ---------------------------------------------------------------------------
# DRF — add browsable API renderer in development
# ---------------------------------------------------------------------------
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (  # type: ignore # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
)

# ---------------------------------------------------------------------------
# Throttling — disable rate limits in development/testing
# ---------------------------------------------------------------------------
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # type: ignore # noqa: F405
    "anon_burst": None,
    "anon_sustained": None,
    "user_burst": None,
    "auth_login": None,
}

# ---------------------------------------------------------------------------
# Logging — more verbose in development
# ---------------------------------------------------------------------------
LOGGING["root"]["level"] = "DEBUG"  # noqa: F405
