# Instagram Backend

A learning-focused, Instagram-style backend built with **FastAPI** as a modular monolith. The long-term goal is to understand and build the backend systems behind a social media feed: media upload and processing, follow graphs, feed generation, ranking, notifications, and analytics.

> **Project status:** This repository is being built incrementally. The architecture below is the target system design and learning roadmap—not a claim that every service or pipeline is already implemented. See [Roadmap.md](Roadmap.md) for delivery status.

## Product vision

Build the backend for a photo-sharing social network where a post travels through this lifecycle:

1. A client requests an upload URL and uploads original media to object storage.
2. Media-processing workers generate resized images, video renditions, thumbnails, and metadata.
3. The post becomes ready and publishes an event.
4. Feed workers use the author's follower graph to distribute or make the post discoverable.
5. A feed request gathers candidate posts, filters and ranks them, then hydrates post and media details.
6. Engagement events—likes, comments, views, follows—feed counters, notifications, analytics, and recommendation learning.

## Target system at a glance

The following image is the project's high-level system-design blueprint. It captures the intended end-to-end architecture—from clients and edge traffic through application services, media processing, hybrid feed generation, event streaming, analytics, and operational concerns. It is a target design that we will implement incrementally, not a representation of currently completed functionality.

![Instagram System Design — target architecture](docs/assets/project-image.png)


The reference system design is intentionally broader than the first implementation. It is split into independently understandable areas:

| Area | Responsibility | Example technologies |
|---|---|---|
| Clients and edge | iOS, Android, web, DNS, CDN, WAF, load balancing, API gateway | HTTPS, CDN, reverse proxy |
| Application services | Auth, profiles, posts, media, stories, likes/comments, follows, feed, ranking, search, notifications | FastAPI modules |
| Data stores | Relational source of truth, cache, graph/follow data, object storage, search index | PostgreSQL, Redis, object storage, search engine |
| Media pipeline | Asynchronous image/video processing and metadata extraction | Queue, workers, FFmpeg, image processing |
| Feed generation | Fan-out-on-write, fan-out-on-read, hybrid candidate generation | Kafka-compatible event bus, Redis |
| Async processing | Notifications, counters, search indexing, moderation, cleanup | Event consumers and background workers |
| Analytics and ML | Event aggregation, recommendation features, ranking experiments | Stream processing, warehouse, feature store |

### Architecture flow

~~~mermaid
flowchart LR
    C[Mobile / Web clients] --> EDGE[DNS / CDN / WAF / Load balancer]
    EDGE --> API[API Gateway / FastAPI]
    API --> AUTH[Auth and User modules]
    API --> POST[Post and Social Graph modules]
    API --> FEED[Feed and Ranking modules]
    POST --> PG[(PostgreSQL)]
    AUTH --> PG
    POST --> OBJ[(Object storage)]
    POST --> BUS[[Event bus]]
    OBJ --> MEDIA[Media processing workers]
    BUS --> MEDIA
    MEDIA --> OBJ
    MEDIA --> PG
    BUS --> FANOUT[Feed fan-out workers]
    FANOUT --> REDIS[(Redis timelines)]
    FEED --> REDIS
    FEED --> PG
    BUS --> ASYNC[Notifications / Counters / Search / Moderation]
    BUS --> ANALYTICS[Analytics and ML pipelines]
~~~

### Feed generation: hybrid fan-out

A central design challenge is balancing write cost against read latency.

~~~mermaid
flowchart TD
    EVENT[post.created event] --> LOOKUP[Look up follower graph]
    LOOKUP --> DECIDE{Author / follower pattern}
    DECIDE -->|Normal account| WRITE[Fan-out on write]
    DECIDE -->|High-follower account| READ[Fan-out on read]
    WRITE --> TIMELINE[(Precomputed Redis timelines)]
    READ --> PULL[Pull recent posts at feed read]
    TIMELINE --> MERGE[Merge candidates]
    PULL --> MERGE
    MERGE --> FILTER[Filter, deduplicate, apply visibility]
    FILTER --> RANK[Rank candidates]
    RANK --> HYDRATE[Hydrate post and media data]
    HYDRATE --> RESPONSE[Return feed page]
~~~

**Why hybrid?** Fan-out-on-write makes reads fast for ordinary accounts but can create enormous write amplification for celebrity accounts. Fan-out-on-read avoids that write amplification but adds read-time work. A hybrid approach uses both paths and merges candidates before filtering and ranking.

## Key system-design principles

- **Start as a modular monolith.** Keep clear module boundaries before introducing networked microservices.
- **PostgreSQL is the source of truth.** Redis is an optimization for cache and timeline access, not the only copy of important domain data.
- **Use object storage for media bytes.** Keep media metadata and ownership in the relational database; serve processed renditions through a CDN.
- **Use events for asynchronous work.** Media processing, feed fan-out, notifications, counters, and indexing should not make the synchronous post request wait for every downstream task.
- **Design for idempotency and retries.** Consumers can receive duplicate events; processing must be safe to retry.
- **Treat feed delivery as a product and systems trade-off.** Ranking quality, freshness, latency, and write amplification must be measured together.
- **Separate authentication from authorization.** Establish who the caller is, then enforce whether that caller can perform the requested action on the resource.
- **Make consistency choices explicit.** A post can be committed before its timeline entries, counters, or analytics are fully updated.

## Current implementation and infrastructure

The repository currently uses a modular-monolith structure:

- `app/` — Python and FastAPI application source code.
- `app/modules/` — domain-oriented modules and their service/repository boundaries.
- `migrations/` — database schema migrations.
- `infra/` — local infrastructure configuration, including Prometheus and Grafana.
- `docs/` — architecture decisions and learning notes.
- [`Roadmap.md`](Roadmap.md) — planned implementation phases.
- [`docs/architecture.md`](docs/architecture.md) — architecture overview and decisions.
- [`docs/learnings/`](docs/learnings/) — detailed engineering learning notes.

The local Docker Compose stack includes the API and supporting infrastructure such as PostgreSQL, Redis, MinIO, Redpanda, pgAdmin, Prometheus, and Grafana. Individual application capabilities are added in roadmap phases; the presence of infrastructure does not mean every pipeline is implemented.

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

The values in `.env.example` are for local development only. Do not use them outside your machine.

## Run the API and infrastructure

```bash
make up
```

API docs are at <http://127.0.0.1:8000/docs>.

Useful local endpoints:

- Liveness: <http://127.0.0.1:8000/api/v1/health>
- Dependency readiness: <http://127.0.0.1:8000/api/v1/ready>
- MinIO console: <http://127.0.0.1:9001>
- pgAdmin: <http://127.0.0.1:5050>
- Prometheus: <http://127.0.0.1:9090>
- Grafana: <http://127.0.0.1:3000>

To run the API outside Docker with hot reload:

```bash
uv run uvicorn app.main:app --reload
```

In another terminal, start PostgreSQL and Redis with:

```bash
docker compose up -d postgres redis
```

## Authentication (first implementation)

The password-based auth slice exposes these routes under `/api/v1`:

| Method | Route | Description |
|---|---|---|
| POST | `/auth/register` | Create a user, password identity, and initial tokens |
| POST | `/auth/login` | Verify email/password and issue tokens |
| POST | `/auth/refresh` | Rotate an opaque refresh token |
| POST | `/auth/logout` | Revoke the refresh-token family |
| GET | `/auth/me` | Return the authenticated user's profile |

Set `AUTH_JWT_SECRET` in your local `.env` to a cryptographically random value of at least 32 bytes (for example, generate one with `openssl rand -hex 32`). Never commit the real secret. Apply the new schema with `make migrate`.

Access tokens are short-lived JWTs. Refresh tokens are opaque values; the database stores only their SHA-256 fingerprints. The API currently returns both tokens in JSON, so native clients should keep refresh tokens in Keychain/Keystore. A browser client needs an HttpOnly/Secure/SameSite cookie transport and CSRF protections before production use. See [the authentication implementation notes](docs/learnings/auth-module-implementation.md) for the flow and known hardening gaps.

## Development checks

```bash
make test
make lint
make typecheck
make migrate
```

`make seed` is intentionally a placeholder until the first domain model and its seed data are defined.

## Learning path

Work through the system in layers rather than trying to build the entire target architecture at once:

1. Users and authentication
2. Posts and media metadata
3. Follow graph and privacy/visibility rules
4. Direct media upload and asynchronous processing
5. Likes, comments, and engagement events
6. Feed read path and baseline ranking
7. Hybrid fan-out and timeline optimization
8. Notifications, counters, and search indexing
9. Observability, load testing, and reliability
10. Analytics and recommendation experiments

For the current next steps, use the [project roadmap](Roadmap.md).