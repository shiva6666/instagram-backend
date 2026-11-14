.PHONY: up down stop logs dev test lint format typecheck migrate seed

up:
	docker compose up --build -d

down:
	docker compose down

stop:
	bash backend/scripts/stop.sh

logs:
	docker compose logs -f

dev:
	bash backend/scripts/dev.sh

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check app tests scripts migrations

format:
	cd backend && uv run ruff format app tests scripts migrations

typecheck:
	cd backend && uv run mypy app/core

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run --extra dev python scripts/seed.py
