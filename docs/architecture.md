# Architecture

The project starts as a modular monolith: one FastAPI process and one PostgreSQL
database, with Redis for cache/timeline experiments. PostgreSQL remains the
source of truth. MinIO, Redpanda, Prometheus, and Grafana are available in the
local Compose environment for later roadmap phases.

## Current backend layout

- `app/api`: HTTP routers and API versioning
- `app/core`: settings, database/cache connections, and logging
- `migrations`: Alembic migration environment
- `tests`: API and integration-oriented tests
- `infra`: local monitoring configuration

Domain modules belong under `app/modules/` as they are introduced. A module
should expose service interfaces to other modules rather than importing another
module's ORM models directly.

## Local dependencies

`docker compose up --build` starts the API and local infrastructure. `/health`
reports process liveness; `/api/v1/ready` reports PostgreSQL and Redis
availability. Database schema changes are applied with `make migrate`.
