# Makefile for GHOST DMPM

.PHONY: help install install-dev test test-unit test-integration test-coverage run clean docker-build docker-run format lint

help:
	@echo "GHOST DMPM - Available commands:"
	@echo "  make install      - Install base package"
	@echo "  make install-dev  - Install with dev dependencies"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run unit tests only"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo "  make run          - Run main application"
	@echo "  make clean        - Clean generated files"
	@echo "  make format       - Format code with black"
	@echo "  make lint         - Run linting checks"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev,crypto,nlp]"

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-coverage:
	pytest tests/ -v --cov=ghost_dmpm --cov-report=term-missing --cov-report=html:test_output/coverage_html

run:
	python main.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage .pytest_cache

docker-build:
	docker build -f docker/Dockerfile -t ghost-dmpm .

docker-run:
	docker-compose -f docker/docker-compose.yml up

format:
	black src/ tests/

lint:
	python -m flake8 src/ tests/ --max-line-length=88 --extend-ignore=E203

# Development shortcuts
dev: install-dev

quick-test:
	pytest tests/unit/test_config.py -v

# For CI/CD
ci-test:
	pytest tests/ --cov=ghost_dmpm --cov-fail-under=70
