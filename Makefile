.PHONY: up down logs test lint format typecheck migrate seed

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy app/core

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/seed.py
