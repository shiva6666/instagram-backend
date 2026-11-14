# Backend application

This directory contains the FastAPI modular monolith, Python dependencies,
Alembic migrations, backend tests, and development scripts.

From the repository root, use the root Makefile:

- `make dev` — start the API and Vite frontend with local PostgreSQL/Redis.
- `make test` — run backend tests.
- `make lint` — run Ruff.
- `make typecheck` — run mypy.
- `make migrate` — apply Alembic migrations.
- `make seed` — populate local demo data.

For direct backend commands, run them from this directory with `uv`.
The local environment file remains at the repository root; application
settings resolve it from the repository location regardless of the process
working directory.
