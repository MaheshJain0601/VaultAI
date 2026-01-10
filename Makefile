# Vault AI - Makefile

.PHONY: help install dev test lint format clean docker-up docker-down init-db run worker flower

# Default target
help:
	@echo "Vault AI - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install dependencies"
	@echo "  make dev-setup   Setup development environment"
	@echo ""
	@echo "Development:"
	@echo "  make run         Start FastAPI development server"
	@echo "  make worker      Start Celery worker"
	@echo "  make flower      Start Flower (Celery monitoring)"
	@echo ""
	@echo "Database:"
	@echo "  make init-db     Initialize database tables"
	@echo "  make migrate     Run database migrations"
	@echo "  make migration   Create new migration"
	@echo ""
	@echo "Testing:"
	@echo "  make test        Run tests"
	@echo "  make test-cov    Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint        Run linters"
	@echo "  make format      Format code"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up   Start all services with Docker"
	@echo "  make docker-down Stop all Docker services"
	@echo "  make docker-logs View Docker logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       Remove generated files"

# Setup
install:
	pip install -r requirements.txt

dev-setup:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cp env.example .env
	@echo "Development environment ready. Edit .env with your settings."

# Development
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A app.workers.celery_app worker --loglevel=info --concurrency=4

flower:
	celery -A app.workers.celery_app flower --port=5555

# Database
init-db:
	python scripts/init_db.py

migrate:
	alembic upgrade head

migration:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# Testing
test:
	pytest -v

test-cov:
	pytest --cov=app --cov-report=html --cov-report=term-missing

# Code Quality
lint:
	black --check app tests
	isort --check-only app tests
	mypy app

format:
	black app tests
	isort app tests

# Docker
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

# Cleanup
clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf storage/documents/*

