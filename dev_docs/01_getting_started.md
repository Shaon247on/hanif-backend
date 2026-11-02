# Getting Started

## Prerequisites

- Python 3.12+
- pip
- PostgreSQL (optional — SQLite used by default in development)
- Redis (optional — required for Celery)

## Setup

### Option 1: Make (Recommended)

```bash
# Create virtual environment
make setup
source .venv/bin/activate

# Install dependencies, copy .env, run migrations
make install

# Start the server
make run
```

### Option 2: Manual

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements/development.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your values

# Run migrations
python manage.py migrate

# Create a superuser (optional)
python manage.py createsuperuser

# Start the server
python manage.py runserver 0.0.0.0:8000
```

## Using Docker (for database services)

Start PostgreSQL and Redis without installing them locally:

```bash
make docker-up    # Starts PostgreSQL + Redis + Adminer
```

Then update your `.env`:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/django_db
CELERY_BROKER_URL=redis://localhost:6379/0
```

## Verification

After starting the server, verify everything works:

- **Health Check**: `http://127.0.0.1:8000/health/` → `{"status": "ok"}`
- **Swagger Docs**: `http://127.0.0.1:8000/swagger/`
- **Admin Panel**: `http://127.0.0.1:8000/admin/`

## Environment Settings

The project uses split settings. Set `DJANGO_SETTINGS_MODULE` in your `.env`:

| Environment | Module | Notes |
|-------------|--------|-------|
| Development | `config.settings.development` | Default. DEBUG=True, SQLite, console emails |
| Staging | `config.settings.staging` | PostgreSQL required, moderate security |
| Production | `config.settings.production` | Full security hardening, HTTPS enforced |
