# Architecture

The project starts as a modular monolith: one FastAPI process and one PostgreSQL
database, with Redis for cache/timeline experiments. PostgreSQL remains the
source of truth. MinIO, Redpanda, Prometheus, and Grafana are available in the
local Compose environment for later roadmap phases.

## Repository boundaries

- `backend/app/api`: HTTP routers and API versioning
- `backend/app/core`: settings, database/cache connections, and logging
- `backend/app/modules`: domain modules and their service/repository boundaries
- `backend/migrations`: Alembic migration environment
- `backend/tests`: API and integration-oriented tests
- `frontend/`: React + TypeScript + Vite client
- `infra/`: local monitoring configuration
- `docs/`: architecture decisions and learning notes

A backend module should expose service interfaces to other modules rather than
importing another module's ORM models directly. The frontend communicates with
the backend through the versioned HTTP API; it does not import backend code.

## Local development

Run `make dev` from the repository root to start PostgreSQL, Redis, FastAPI,
and Vite. Run `docker compose up --build` to start the API and local
infrastructure. `/health` reports process liveness; `/api/v1/ready` reports
PostgreSQL and Redis availability. Database schema changes are applied with
`make migrate`.
