.PHONY: help install install-dev update lock test test-coverage lint format run run-prod \
        docker-build docker-run docker-down docker-logs load-test clean fmt lint-fix lint-check \
        export-requirements

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	poetry install --only main
	poetry run pre-commit install

install-dev: ## Install all dependencies including dev tools
	poetry install

update: ## Update dependencies
	poetry update

lock: ## Update lock file
	poetry lock

test: ## Run tests with coverage
	poetry run pytest -v

test-coverage: ## Run tests and check coverage threshold
	poetry run pytest --cov=app --cov-report=html --cov-report=term
	poetry run coverage report --fail-under=85

lint: ## Run linters
	poetry run black --check .
	poetry run isort --check-only .
	poetry run flake8 .

fmt: ## Auto-format code (isort, black, autoflake, ruff)
	poetry run isort .
	poetry run black .
	poetry run autoflake --in-place --remove-unused-variables --remove-all-unused-imports -r .
	poetry run ruff check --fix

lint-check: ## Run strict lint checks without modifying files
	poetry run flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	poetry run black --check .
	poetry run isort --check-only .

run: ## Run development server
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build: ## Build Docker image
	docker build -t realtime-voice-pipeline .

docker-run: ## Run with Docker Compose
	docker compose up

docker-down: ## Stop Docker containers
	docker compose down

docker-logs: ## View Docker logs
	docker compose logs -f

load-test: ## Run load tests
	poetry run locust -f tests/load_test.py --headless -u 50 -r 5 -t 60s --host http://localhost:8000

clean: ## Clean temporary files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf htmlcov .coverage coverage.xml dist build

export-requirements:
	poetry export -f requirements.txt --output requirements.txt --without-hashes