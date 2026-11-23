# Architecture

The project is a modular monolith: one FastAPI application and one PostgreSQL
database. PostgreSQL is the source of truth for users, posts, relationships,
and media metadata. Redis is used for cache/timeline experiments. MinIO is the
local S3-compatible object store for private media bytes. Redpanda, Prometheus,
and Grafana are available in the local Compose environment for later roadmap
phases; their presence does not mean the application already depends on them.

## Repository boundaries

- `backend/app/api`: HTTP routers and API versioning
- `backend/app/core`: settings, database/cache connections, and logging
- `backend/app/modules`: domain modules and their service/repository boundaries
- `backend/migrations`: Alembic migration environment
- `backend/tests`: API and integration-oriented tests
- `frontend/`: React + TypeScript + Vite client
- `infra/`: local monitoring configuration
- `docs/adr/`: accepted architecture decisions and their trade-offs
- `docs/learnings/`: learning notes

A backend module should expose service interfaces to other modules rather than
importing another module's ORM models directly. The frontend communicates with
the backend through the versioned HTTP API; it does not import backend code.

## Media architecture

The image lifecycle is implemented in the active `backend/` application. See
[ADR 0004: Image media upload and delivery lifecycle](adr/0004-image-media-lifecycle.md)
for the full rationale, API contract, state transitions, failure boundaries,
and follow-up work.

Key decisions:

- The browser uploads directly to a private MinIO/S3 bucket using a short-lived
  presigned PUT URL; the FastAPI process does not proxy image bytes.
- PostgreSQL stores media ownership, lifecycle state, expected/actual metadata,
  and object keys. Object storage stores original and processed bytes.
- The media module owns upload lifecycle, validation, processing orchestration,
  and signed URL resolution. Posts attach READY media through a relational
  `post_media` association.
- The processor accepts JPEG, PNG, and WebP single-frame images, validates
  signatures and decoded format, enforces size/dimension/pixel limits, strips
  metadata, and writes WebP display and thumbnail variants.
- The bucket stays private. Post/feed visibility checks run before short-lived
  signed GET URLs are generated.
- Existing URL-based post images remain supported for compatibility.
- Cleanup is a retryable scheduled job. It claims rows as DELETING, deletes
  objects idempotently, and removes metadata only after successful deletion.

Image processing currently runs synchronously during completion. PR #14 added failure-path coverage for invalid content, missing expired uploads, transient storage-read failures, and partial variant writes. The current transaction rolls back an uncommitted PROCESSING state, so a stale-PROCESSING sweeper is not part of this design. Cleanup deletion-failure/retry integration coverage, operational metrics, and any durable worker/outbox remain follow-up work. See ADR 0004 for the current failure and retry contract.

## Local development

Run `make dev` from the repository root to start PostgreSQL, Redis, FastAPI,
and Vite. Run `docker compose up --build` to start the API and local
infrastructure. `/health` reports process liveness; `/api/v1/ready` reports
PostgreSQL and Redis availability. Database schema changes are applied with
`make migrate`.

For media development, the local Compose stack also starts MinIO and configures
the API's internal storage endpoint separately from the public endpoint used
by browser-facing presigned URLs. Run `make cleanup-media` to execute one
cleanup pass; schedule it periodically in a deployed environment.
