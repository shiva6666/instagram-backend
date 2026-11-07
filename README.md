# Instagram Backend

A modular-monolith Instagram-style backend built with FastAPI. PostgreSQL is the
source of truth; Redis and the local infrastructure stack support later roadmap
phases.

## Repository layout

- `app/` — Python and FastAPI application source code.
- `infra/` — configuration for local infrastructure, including Prometheus and
  Grafana.
- `docs/` — project documentation; add personal notes in
  [`docs/learnings/`](docs/learnings/).
- `scripts/` — helper commands, when the project includes them.
- [`docker-compose.yml`](docker-compose.yml) — connects the API with the
  database, cache, file storage, event broker, and monitoring services.

## Requirements

- Python 3.15+
- [uv](https://docs.astral.sh/uv/)
- Docker Compose

## Setup

```bash
cp .env.example .env
uv sync --extra dev
pre-commit install
```

The values in `.env.example` are local-development credentials only. Do not use
them outside your machine.

## Run the API and infrastructure

```bash
make up
```

`make up` starts the API, PostgreSQL, Redis, MinIO, Redpanda, pgAdmin,
Prometheus, and Grafana. API docs are at <http://127.0.0.1:8000/docs>.

Useful local endpoints:

- Liveness: <http://127.0.0.1:8000/api/v1/health>
- Dependency readiness: <http://127.0.0.1:8000/api/v1/ready>
- MinIO console: <http://127.0.0.1:9001>
- pgAdmin: <http://127.0.0.1:5050>
- Prometheus: <http://127.0.0.1:9090>
- Grafana: <http://127.0.0.1:3000>

Run the API outside Docker for hot reload with `uv run uvicorn app.main:app
--reload`. In that case, start PostgreSQL and Redis with
`docker compose up -d postgres redis`.

## Development checks

```bash
make test
make lint
make typecheck
make migrate
```

`make seed` is intentionally a placeholder until the first domain model and its
seed data are defined. See [the roadmap](Roadmap.md) and
[architecture notes](docs/architecture.md) for the next steps.
