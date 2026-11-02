#!/usr/bin/env bash
# =============================================================================
# Docker entrypoint script
# =============================================================================
set -e

echo "⏳ Waiting for database..."
python scripts/wait_for_db.py

echo "📦 Running migrations..."
python manage.py migrate --no-input

echo "📁 Collecting static files..."
python manage.py collectstatic --no-input

echo "🚀 Starting server..."
exec "$@"
