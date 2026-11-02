# ==============================================================================
# Django Template — Makefile
# ==============================================================================

.PHONY: setup run test lint format migrate shell docker-up docker-down celery

PYTHON ?= python
PIP ?= pip
MANAGE = $(PYTHON) manage.py
SETTINGS ?= config.settings.development

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

setup: ## First-time project setup
	$(PYTHON) -m venv .venv
	@echo "Activate venv: source .venv/bin/activate"
	@echo "Then run: make install"

install: ## Install dependencies
	$(PIP) install -r requirements/development.txt
	@test -f .env || cp .env.example .env
	$(MANAGE) migrate
	@echo "✅ Setup complete. Run: make run"

run: ## Start development server
	$(MANAGE) runserver 0.0.0.0:8000

test: ## Run tests with coverage
	DJANGO_SETTINGS_MODULE=$(SETTINGS) pytest --cov=apps --cov-report=term-missing -v

lint: ## Run linter
	ruff check apps/ config/

format: ## Format code
	ruff format apps/ config/
	ruff check --fix apps/ config/

migrate: ## Run makemigrations + migrate
	$(MANAGE) makemigrations
	$(MANAGE) migrate

shell: ## Django shell
	$(MANAGE) shell

superuser: ## Create superuser
	$(MANAGE) createsuperuser

collectstatic: ## Collect static files
	$(MANAGE) collectstatic --no-input

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

docker-up: ## Start dev services (PostgreSQL, Redis)
	docker compose up -d

docker-down: ## Stop dev services
	docker compose down

docker-build: ## Build production Docker image
	docker build -t django-template .

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

celery: ## Start Celery worker
	celery -A config worker --loglevel=info --concurrency=4

celery-beat: ## Start Celery beat scheduler
	celery -A config beat --loglevel=info

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
