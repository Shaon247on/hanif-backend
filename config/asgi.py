"""ASGI config."""

import os
from pathlib import Path

import environ
from django.core.asgi import get_asgi_application

# Load .env file before setting DJANGO_SETTINGS_MODULE
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

application = get_asgi_application()
