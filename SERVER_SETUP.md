# Server Setup Guide

Welcome to the server setup guide for the **BarberBay** backend. This project is built with Django, PostgreSQL, Redis, and Celery. 

You can set up the development environment in two ways: **Local Setup (Virtual Environment)** or **Full Docker Setup**.

---

## Prerequisites
- **Python 3.x**
- **Docker & Docker Compose** (Required for PostgreSQL and Redis)
- **Make** utility

---

## Method 1: Local Setup (Using Virtual Environment & Makefile)

This is the recommended approach for active development, utilizing the built-in `Makefile`.

### 1. Initialize the Virtual Environment
Create the `.venv` directory:
```bash
make setup
```

### 2. Activate the Virtual Environment
**On Linux/macOS:**
```bash
source .venv/bin/activate
```
**On Windows:**
```bash
.venv\Scripts\activate
```

### 3. Start Database & Redis Services
The backend requires PostgreSQL and Redis. Start them in the background using Docker:
```bash
make docker-up
```

### 4. Install Dependencies & Setup DB
This command will install all required Python packages (from `requirements/development.txt`), copy `.env.example` to `.env`, and apply all Django database migrations.
```bash
make install
```

### 5. Create a Superuser
To access the Django admin panel, create a superuser account:
```bash
make superuser
```

### 6. Run the Development Server
```bash
make run
```
The server will now be available at `http://localhost:8000/`.

### 7. Run Celery Workers (For Background Tasks)
If you are testing background tasks, open a separate terminal (with the venv activated) and run:
```bash
make celery
```
For scheduled tasks, run the Celery Beat scheduler:
```bash
make celery-beat
```

---

## Method 2: Full Docker Setup

If you prefer to run the entire stack (Django Web, Celery, Postgres, Redis, Adminer) containerized:

### 1. Configure Environment Variables
```bash
cp .env.example .env
```

### 2. Start All Services
Build and start the containers in the background:
```bash
docker compose up -d --build
```

### 3. Run Migrations & Setup
Apply migrations and create a superuser inside the web container:
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

### 4. Access the Application
- **API/Web**: `http://localhost:8000/`
- **Database GUI (Adminer)**: `http://localhost:8080/`

### 5. Stop the Services
To stop and remove the containers:
```bash
make docker-down
# OR: docker compose down
```

---

## Useful Development Commands

You can run these commands directly from your terminal using `make`:

- `make lint` : Check code quality using Ruff
- `make format` : Auto-format code using Ruff
- `make test` : Run Pytest test suite with coverage reports
- `make shell` : Open the interactive Django shell
- `make migrate` : Generate and apply database migrations (`makemigrations` + `migrate`)
- `make collectstatic` : Collect static files
