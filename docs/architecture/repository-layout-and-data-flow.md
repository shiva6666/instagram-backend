# Repository layout and request data flow

## One source of truth

The canonical backend project lives entirely under `backend/`.

- Application entry point: `backend/app/main.py`
- API composition root: `backend/app/api/router.py`
- Domain modules: `backend/app/modules/`
- Shared infrastructure: `backend/app/core/`
- Persistence migrations: `backend/migrations/`
- Automated tests: `backend/tests/`
- Development and operational scripts: `backend/scripts/`
- Python dependencies and tooling: `backend/pyproject.toml` and `backend/uv.lock`

The repository root is reserved for cross-project orchestration and shared assets: `frontend/`, `docs/`, `infra/`, `docker-compose.yml`, `Makefile`, root environment files, and repository-level configuration.

There is no second Python project at the root. Root-level legacy copies of `app/`, `tests/`, `scripts/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, and `alembic.ini` were removed because they were stale duplicates and were not the project used by the current launcher, Docker Compose service, or CI job.

## Why two trees existed

The Git history shows that the repository originally had a root-level Python application and tooling. Later, the backend was organized as a self-contained project under `backend/`, with its own application, dependencies, migrations, tests, Dockerfile, and scripts. The root-level copy was not removed during that reorganization, so both paths remained visible.

That created two competing sources of truth:
- The root `app/` had an older, incomplete module set and did not register the likes or media routers.
- The active `backend/app/` contained the current modules and router registrations.
- Root-level tests and scripts duplicated the versions under `backend/`.
- Root-level Python project files could mislead tools into resolving the wrong project.

The original split was therefore a historical repository-layout artifact, not an intentional two-service or two-package architecture. It is not needed for the modular monolith.

## Runtime startup flow

```text
Repository root
  ├── Makefile: make dev
  │     └── backend/scripts/dev.sh
  │           ├── starts PostgreSQL, Redis, MinIO with root docker-compose.yml
  │           ├── changes working directory to backend/
  │           ├── syncs backend/pyproject.toml + backend/uv.lock
  │           ├── runs Alembic migrations from backend/migrations/
  │           ├── starts uvicorn app.main:app
  │           └── starts frontend Vite dev server
  │
  ├── docker-compose.yml
  │     └── app service builds backend/Dockerfile
  │           └── copies backend/app into image and starts app.main:app
  │
  └── .github/workflows/ci.yml
        └── backend job working-directory: backend/
              ├── Ruff / mypy
              ├── Alembic migration
              └── pytest
```

## HTTP request data flow

```text
Browser (React + TypeScript)
  │
  │ /api/v1/... (Vite proxy in development)
  ▼
backend/app/main.py
  │ creates FastAPI app and includes api_router at settings.api_v1_prefix
  ▼
backend/app/api/router.py
  │ composes health, auth, users, posts, likes, media, follows, feed routers
  ▼
Domain router
  │ parses HTTP input, resolves dependencies, maps domain errors to HTTP
  ▼
Service / use case
  │ enforces business rules and coordinates module contracts
  ▼
Repository Protocol / SQLAlchemy adapter
  │ translates domain operations into SQL
  ▼
PostgreSQL
  │ durable source of truth
  └── External object storage (MinIO) for media bytes where the use case requires it
```

### Example: liking a post

```text
POST /api/v1/posts/{post_id}/like
  → backend/app/main.py mounts api_router under /api/v1
  → backend/app/api/router.py includes likes_router
  → backend/app/modules/likes/router.py resolves authenticated User + LikeService
  → LikeService asks PostService to enforce post visibility
  → SqlAlchemyLikeRepository inserts (user_id, post_id)
  → PostgreSQL composite primary key prevents duplicate likes
  → request-scoped DB dependency commits on success / rolls back on error
  → LikeStatusResponse returns post_id, liked, like_count
```

## Module responsibilities

- **main.py:** process/application composition and lifespan only; it does not contain domain rules.
- **api/router.py:** top-level route composition. Every module router must be included here to expose its endpoints.
- **router.py inside a module:** HTTP contract and dependency wiring for that module.
- **service.py:** use-case orchestration, validation and business invariants.
- **repository.py:** persistence port/protocol and SQLAlchemy implementation.
- **models.py:** domain objects and/or ORM mappings according to the module's established conventions; keep persistence rows out of cross-module contracts.
- **core/:** shared configuration, database/session, security and infrastructure primitives.
- **migrations/:** schema evolution; migrations are not run from the repository root.

## Supported commands

Run these from the repository root:

- `make dev` — local API + frontend development.
- `make stop` — stop local development processes.
- `make test` — backend test suite.
- `make lint` / `make format` — backend Ruff.
- `make typecheck` — backend mypy checks.
- `make migrate` — apply backend Alembic migrations.
- `make seed` — seed local demo data.
- `docker compose up --build` — containerized stack.

For direct Python commands, first `cd backend` and use `uv`. Do not run Python tooling from the repository root; there is no root Python project anymore.

## Boundary rule

When adding a backend feature, create it under `backend/app/modules/<module>/`, register its router in `backend/app/api/router.py`, add tests under `backend/tests/`, add schema changes under `backend/migrations/`, and update the relevant ADR/learning note. Do not recreate root-level backend folders.
