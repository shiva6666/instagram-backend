# Roadmap: Instagram-Style Modular Monolith (12 Weeks)

A task-by-task plan for building a modular FastAPI monolith with a React + TypeScript client, learning alongside *Designing Data-Intensive Applications* (DDIA) and Alex Xu's *System Design Interview* (Vol 1, Vol 2 where noted).

**Start date:** ____ **Target finish:** ____

## Progress overview

| Phase | Week | Theme | Status |
|---|---|---|---|
| Setup | 0 | Repo, Compose, CI | In progress |
| 1: Single-node correctness | 1 | Estimation + data model | [ ] |
| | 2 | Auth, users, posts | [ ] |
| | 3 | Follow graph + naive feed (baseline) | [ ] |
| | 4 | Media upload pipeline | [ ] |
| 2: Fast and distributed | 5 | Fan-out on write, Redis timelines | [ ] |
| | 6 | Hybrid fan-out for celebrities | [ ] |
| | 7 | Replication, read-your-writes | [ ] |
| | 8 | Transactions, counters, idempotency, rate limiter | [ ] |
| 3: Events and resilience | 9 | Event bus and async workers | [ ] |
| | 10 | Notifications and counters via events | [ ] |
| | 11 | Failure drills | [ ] |
| | 12 | Observability, hardening, interview packaging | [ ] |

## How to use this roadmap

- Each week has **Goal, Tasks, Tools, Read, and Exit criteria**. Do not start the next week until the exit criteria are met.
- **Weekly rhythm:** 3 build days, 1 DDIA day, 1 Xu day, weekend for "break it, measure it, write an ADR".
- **ADR** = one-page Architecture Decision Record in `docs/adr/`: context, options, decision, numbers, consequences.
- Write the core of every phase by hand. Use Claude Code as reviewer, test writer, and boilerplate generator, not as the author of the hard parts.
- Measure before and after every optimization. Save results in `docs/benchmarks/`.

## Scope: what we build vs. what we only study

**Build:** auth, profiles, posts with media, follow graph, likes/comments, hybrid fan-out feed, cursor pagination, Redis timelines and counters, event bus, async workers, notifications, rate limiting, observability, load tests.

**Study only (from the system design diagram):** DNS/GeoDNS, CDN, WAF/DDoS, multi-region replication, Cassandra, Elasticsearch, ML ranking and training, moderation pipeline, video transcoding.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language / tooling | Python 3.12, `uv`, Ruff, mypy, pre-commit | Fast, typed, lint-clean from day 1 |
| API | FastAPI, Pydantic v2, Uvicorn/Gunicorn | Typed request/response models (like Zod + TS) |
| ORM / DB access | SQLAlchemy 2.0 (async), asyncpg, Alembic | Real migrations, explicit queries |
| Primary DB | PostgreSQL 16 | Source of truth |
| Cache / timelines | Redis 7 (sorted sets, hashes, Lua) | Timelines, counters, rate limits |
| Object storage | MinIO (S3-compatible), aioboto3 | Presigned uploads |
| Event bus | Redpanda (Kafka API), aiokafka | Simple local Kafka |
| Image processing | Pillow | Resize, thumbnails, EXIF strip |
| Auth | JWT (access + refresh), argon2 hashing | Standard, interview-friendly |
| Testing | pytest, pytest-asyncio, httpx, Testcontainers, Hypothesis | Real DBs in tests |
| Observability | structlog, Prometheus, Grafana, OpenTelemetry (optional) | Metrics and logs |
| Load testing | Locust or k6 | Before/after numbers |
| Frontend | Vite, React 18, TypeScript, TanStack Query, React Router, Zod, Tailwind | Your home turf |
| API client | `openapi-typescript` generated from FastAPI's OpenAPI | End-to-end types |
| Frontend tests | Vitest, React Testing Library, MSW, Playwright | Unit, integration, e2e |
| Infra / CI | Docker Compose, GitHub Actions | Reproducible dev and CI |

## Target repo layout

```
repo/
  backend/
    app/
      core/          # config, db, redis, security, logging
      modules/
        auth/  users/  posts/  media/  graph/
        feed/  engagement/  notifications/
      workers/       # fanout, media, notifications consumers
      main.py
    migrations/  tests/
  frontend/
  infra/             # compose files, grafana dashboards, prometheus.yml
  docs/
    adr/  benchmarks/  drills/  estimation.md  architecture.md
  Makefile
  roadmap.md
```

Rule: modules talk to each other through a small `service.py` interface only, never by importing another module's models directly. This keeps the monolith splittable later.

---

## Week 0: Setup (2 to 3 days, before Week 1)

**Goal:** a repo where one command starts everything.

- [ ] Create monorepo with `backend/`, `frontend/`, `infra/`, `docs/`
- [ ] Create monorepo with `backend/`, `frontend/`, `infra/`, `docs/` (existing backend package layout retained)
- [x] `docker-compose.yml` with Postgres, Redis, MinIO, Redpanda, pgAdmin, Prometheus, Grafana
- [x] Add FastAPI, SQLAlchemy, asyncpg, Alembic, pydantic-settings, structlog
- [x] Config via `pydantic-settings` (`.env`, no hardcoded secrets)
- [x] `/health` and `/ready` endpoints (ready checks Postgres + Redis)
- [x] Ruff + mypy (strict on `app/core`) + pre-commit hooks
- [x] GitHub Actions: lint, type-check, test on every PR
- [x] `Makefile`: `make up`, `make test`, `make migrate`, `make seed`
- [ ] Vite + React + TS scaffold; generate API client from OpenAPI
- [x] Create `docs/estimation.md` and `docs/adr/0001-modular-monolith.md`

**Exit criteria:** `make up` boots all services; CI is green on an empty test.

---

# Phase 1: Single-node correctness (Weeks 1 to 4)

## Week 1: Estimation and data model

**Goal:** design before code, with numbers.

**Read:** DDIA: reliability/scalability/maintainability, data models and query languages. Xu Vol 1: *Scale From Zero to Millions*, *Back-of-the-Envelope Estimation*.

- [ ] Write `docs/estimation.md`: DAU, posts/day, avg followers, read:write ratio, storage/year, peak QPS, timeline memory in Redis
- [ ] Draw ER diagram: users, posts, media, follows, likes, comments, notifications
- [ ] Write Alembic migration 001 (users, posts, follows) with proper constraints and FKs
- [ ] Decide ID strategy (UUIDv7 or snowflake-style) and write an ADR (links to Xu *Unique ID Generator*)
- [ ] Add indexes you can justify: `(author_id, created_at DESC)`, follows `(follower_id)` and `(followee_id)`
- [ ] Write a seed script (Faker): 10k users, 1M posts, power-law follower counts
- [ ] Repository + service pattern for `users` module with unit tests

**Tools:** Alembic, SQLAlchemy, Faker, dbdiagram.io or Mermaid, pgAdmin.

**Exit criteria:** estimation doc re-reviewed after 24 hours (fix mistakes); seed script loads 1M posts in under 10 minutes.

## Week 2: Auth, users, posts CRUD

**Read:** DDIA: encoding and evolution (schema evolution, forward/backward compatibility).

- [ ] Register, login, refresh, logout endpoints (argon2 hashing, JWT access + refresh rotation)
- [ ] Auth dependency (`get_current_user`) and owner-only permission checks
- [ ] User profile GET/PATCH, avatar placeholder field
- [ ] Posts: create, get, delete (soft delete), list by author
- [ ] Pydantic request/response schemas separate from ORM models
- [ ] Consistent error format (RFC 7807-style problem details) and global exception handlers
- [ ] Request ID middleware + structured logs with request id and user id
- [ ] Integration tests with Testcontainers (real Postgres)
- [ ] Frontend: login/register pages, auth context, token refresh interceptor, protected routes

**Tools:** FastAPI dependencies, argon2-cffi, PyJWT, Testcontainers, React Router, TanStack Query.

**Exit criteria:** can register, log in, create a post from the UI; 80%+ coverage on auth and posts services.

## Week 3: Follow graph and the naive feed (your baseline)

**Read:** DDIA: storage and retrieval (B-trees vs LSM-trees, indexes).

- [ ] Follow/unfollow endpoints (idempotent, unique constraint, no self-follow)
- [ ] Followers/following lists with **cursor pagination** (keyset on `(created_at, id)`)
- [ ] Naive feed query: posts from followed users, ordered by time, via JOIN
- [ ] `EXPLAIN (ANALYZE, BUFFERS)` on every query; record plans in `docs/benchmarks/week3.md`
- [ ] Load test with Locust: 100 concurrent users reading feeds; record p50/p95/p99 and QPS
- [ ] Compare OFFSET vs keyset pagination at deep pages and document it
- [ ] Frontend: home feed with `useInfiniteQuery`, skeleton loading, empty/error states

**Tools:** Postgres EXPLAIN, Locust or k6, `pg_stat_statements`, TanStack Query.

**Exit criteria:** a saved baseline (e.g. "naive feed p95 = X ms at Y QPS with 1M posts"). Every later optimization is measured against this number.

## Week 4: Media upload pipeline (synchronous version)

**Read:** Xu Vol 1: object storage / queue concepts; review your DDIA notes from Phase 1.

- [ ] `media` module: request presigned PUT URL, client uploads straight to MinIO
- [ ] `POST /media/complete` marks upload done and creates a `processing` media row
- [ ] Pillow worker (in-process for now): resize to 3 widths, WebP output, thumbnail, strip EXIF
- [ ] Post states: `PENDING_MEDIA` to `READY`; posts hidden from feeds until `READY`
- [ ] Validate content type, size limits, magic-bytes check (never trust the extension)
- [ ] Immutable, versioned object keys (`media/{id}/{variant}-{hash}.webp`)
- [ ] Frontend: upload component with progress bar, retry, optimistic preview
- [ ] ADR: why presigned uploads bypass the API server
- [ ] Phase 1 retro: write `docs/architecture.md` v1 with a diagram

**Tools:** MinIO, aioboto3, Pillow, `python-magic`, XHR/axios for upload progress.

**Exit criteria:** end-to-end "create post with image" works from the UI; Phase 1 retro written.

---

# Phase 2: Fast and distributed (Weeks 5 to 8)

## Week 5: Fan-out on write with Redis timelines

**Read:** DDIA: replication (leaders and followers). Xu Vol 1: *Design a News Feed System*.

- [ ] Redis timeline per user: sorted set `timeline:{user_id}` (score = timestamp, member = post_id), capped at ~800 items
- [ ] Fan-out worker: on post READY, fetch followers in batches, `ZADD` via pipeline
- [ ] Feed read path: `ZREVRANGEBYSCORE` for cursor, then hydrate posts from Postgres (batch fetch, no N+1)
- [ ] Post-hydration cache (Redis hash or JSON) with TTL and cache-aside
- [ ] Handle delete: remove from timelines or filter at hydrate time (document your choice in an ADR)
- [ ] Rebuild-timeline job for a user (needed for inactive users and recovery)
- [ ] Re-run the Week 3 load test; write `docs/benchmarks/week5.md` comparing against baseline

**Tools:** Redis sorted sets, redis-py asyncio, pipelines, Locust.

**Exit criteria:** feed p95 is at least 10x better than baseline, with a documented table.

## Week 6: Hybrid fan-out for celebrities

**Read:** Xu news feed chapter again (celebrity problem); DDIA: partitioning (skew and hot spots).

- [ ] Threshold config (e.g. `CELEBRITY_FOLLOWER_THRESHOLD`) and a flag for users crossing it
- [ ] Skip push for celebrity authors; store their recent posts in an `author_recent:{id}` sorted set
- [ ] Read path merges pushed timeline + recent posts from followed celebrities, then dedupes and sorts
- [ ] Skip fan-out to inactive followers (no login in N days); rebuild on next login
- [ ] Seed a few accounts with 100k+ followers; measure fan-out time with and without hybrid
- [ ] Edge cases: user crosses the threshold, unfollows a celebrity, deletes a post
- [ ] ADR: push vs pull vs hybrid, with measured write amplification

**Tools:** Redis (Lua optional for atomic merge), Locust scenarios for celebrity posts.

**Exit criteria:** a celebrity post does not create millions of writes; feed correctness tests pass for both paths.

## Week 7: Replication and read-your-writes

**Read:** DDIA: replication lag, read-your-writes, monotonic reads.

- [ ] Postgres streaming replica in Docker Compose
- [ ] Router: reads to replica, writes to primary, configurable per endpoint
- [ ] Inject artificial lag (`pg_wal_replay_pause` or network delay) and **reproduce a stale-read bug** (you post, refresh, post missing)
- [ ] Fix with read-your-writes: pin the author's reads to primary for N seconds after a write (or track LSN)
- [ ] Monotonic reads test: user does not see the feed go "back in time"
- [ ] Frontend: optimistic insert of your own post into the feed cache (TanStack Query `setQueryData`)
- [ ] ADR: consistency guarantees per endpoint (feed vs profile vs post detail)

**Tools:** Postgres replication, `pg_stat_replication`, Toxiproxy (optional), TanStack Query.

**Exit criteria:** a written test that fails without your fix and passes with it.

## Week 8: Transactions, counters, idempotency

**Read:** DDIA: transactions (isolation levels, write skew, lost updates). Xu Vol 1: *Design a Rate Limiter*, *Consistent Hashing*.

- [ ] Likes: unique `(user_id, post_id)` constraint; idempotent like/unlike
- [ ] Comments: create, list with cursor pagination, soft delete
- [ ] Denormalized counters (`like_count`) updated via Redis `INCR`, flushed to Postgres periodically
- [ ] **Reproduce a lost-update race** with concurrent requests, then fix (atomic SQL, `SELECT ... FOR UPDATE`, or Redis atomics)
- [ ] `Idempotency-Key` header on write endpoints (store key and response in Redis with TTL)
- [ ] Rate limiter v1: token bucket in Redis via Lua script, per user and per IP
- [ ] Return `429` with `Retry-After`; decide fail-open vs fail-closed per endpoint (ADR)
- [ ] Consistent hashing: implement a small ring in a script (study only, not wired in)

**Tools:** Postgres isolation levels, Redis Lua, pytest with `asyncio.gather` for race tests, Hypothesis.

**Exit criteria:** race tests reproduce the bug and prove the fix; rate limiter holds under a Locust burst.

---

# Phase 3: Events, resilience, production-ness (Weeks 9 to 12)

## Week 9: Event bus and async workers

**Read:** DDIA: stream processing, event logs, derived data.

- [ ] Event schemas (Pydantic models) with `event_id`, `type`, `version`, `occurred_at`, `payload`
- [ ] **Transactional outbox:** write the event to an `outbox` table in the same DB transaction; a relay publishes to Redpanda
- [ ] Topics: `post.created`, `media.uploaded`, `media.processed`, `like.created`, `comment.created`, `follow.created`
- [ ] Move fan-out and media processing from in-process to consumers (`aiokafka`, consumer groups)
- [ ] Idempotent consumers (processed-event table or natural idempotency)
- [ ] Retry with exponential backoff; dead-letter topic after N failures; a small DLQ inspection script
- [ ] Choose partition keys deliberately (e.g. `author_id`) and document ordering guarantees

**Tools:** Redpanda, aiokafka, `rpk` CLI, Redpanda Console.

**Exit criteria:** kill and restart a worker mid-stream with no lost or duplicated timeline entries.

## Week 10: Notifications and counters via events

**Read:** Xu Vol 1: *Design a Notification System*. DDIA: batch vs stream review.

- [ ] `notifications` table + inbox endpoints (list, mark read, unread count)
- [ ] Notification consumer: like/comment/follow events to in-app notifications
- [ ] Aggregate noisy events ("Alice and 12 others liked your post") with a time window
- [ ] Per-user preferences (mute types)
- [ ] Real-time delivery to the browser via SSE or WebSocket (pick one, write an ADR)
- [ ] Counter aggregation consumer: batch like/view counts into Redis then Postgres
- [ ] Frontend: notification bell, unread badge, live updates, `useEffect` cleanup for connections
- [ ] Stub a push-notification provider interface (no real FCM/APNs)

**Tools:** SSE (`sse-starlette`) or FastAPI WebSockets, Redis pub/sub, aiokafka.

**Exit criteria:** liking a post triggers a live notification within a couple of seconds, with idempotent processing.

## Week 11: Failure drills

**Read:** DDIA: the trouble with distributed systems; consistency and consensus (skim, focus on concepts).

- [ ] Timeouts on every outbound call (DB, Redis, Kafka, MinIO); retries with jitter
- [ ] Circuit breaker around the Redis feed path, with fallback to the Postgres query (degraded but working)
- [ ] Graceful shutdown for workers (finish in-flight message, commit offset)
- [ ] **Drills, each with a short write-up in `docs/drills/`:**
  - [ ] Kill Redis: feed still loads (slower)
  - [ ] Kill a worker: lag grows, then recovers on restart
  - [ ] Pause Postgres replica: stale reads handled
  - [ ] Poison message: lands in DLQ, partition not blocked
  - [ ] Replay the event log to rebuild timelines from scratch
- [ ] Verify rate limiter behavior when Redis is down (matches your ADR decision)
- [ ] Back up and restore Postgres once (`pg_dump`, PITR concept) and document the steps

**Tools:** Toxiproxy, `docker compose kill/pause`, `tenacity` or custom retry, Locust.

**Exit criteria:** five drill reports, each with symptoms, cause, fix.

## Week 12: Observability, hardening, interview packaging

**Read:** revisit your DDIA notes and Xu chapters; redo two designs from memory on paper.

- [ ] Metrics: request rate/latency/errors per endpoint, DB pool usage, Redis latency, consumer lag, queue depth
- [ ] Grafana dashboard JSON committed to `infra/`
- [ ] Alert rules (written even if not routed): p95 latency, error rate, consumer lag
- [ ] Security pass: CORS, security headers, input limits, dependency audit (`pip-audit`, `npm audit`), secrets scan
- [ ] Pagination, N+1, and index review using `pg_stat_statements`
- [ ] Final load test with the full stack; publish a benchmark table (baseline vs final)
- [ ] Playwright e2e: register, post with image, follow, see in feed, like, notification arrives
- [ ] README with architecture diagram, how to run, decisions index, benchmark highlights
- [ ] Final `docs/architecture.md`: what you would change to go to 10x, then 100x (sharding, Cassandra, CDN, multi-region)
- [ ] Mock interview: design "Instagram" in 45 minutes using this project as your evidence

**Tools:** Prometheus, Grafana, `prometheus-fastapi-instrumentator`, Playwright, pip-audit.

**Exit criteria:** a stranger can clone, run `make up`, and see a working app plus dashboards.

---

## Backend quality bar (apply every week)

- [ ] Every endpoint has a typed schema, an integration test, and a documented error case
- [ ] No business logic in routers; routers call services, services call repositories
- [ ] Every migration is reversible and tested on seeded data
- [ ] No N+1 queries (add a test helper that counts queries)
- [ ] Every background job is idempotent
- [ ] Every config value comes from the environment
- [ ] Logs are structured and contain a request or event id

## Frontend quality bar (apply every week)

- [ ] Types generated from OpenAPI; no hand-written API types
- [ ] Server state in TanStack Query only; local state stays local
- [ ] Loading, empty, error, and offline states for every screen
- [ ] Accessible by default (labels, focus management, keyboard)
- [ ] Component tests for logic-heavy components; one Playwright flow per major feature

## Final deliverables checklist

- [ ] Working monolith + React client running via Docker Compose
- [ ] 10+ ADRs
- [ ] Estimation doc and architecture doc
- [ ] Benchmark report (baseline vs optimized)
- [ ] 5 failure-drill write-ups
- [ ] Grafana dashboard
- [ ] CI green with lint, types, unit, integration, e2e
- [ ] README and a short walkthrough video or blog post

## If you fall behind

**Cut, in this order:** the Week 10 push-provider stub, SSE/WebSocket live updates, Week 7 Toxiproxy work, Playwright e2e.

**Never cut:** the baseline benchmark (Week 3), hybrid fan-out (Week 6), the race-condition tests (Weeks 7 and 8), and the failure drills (Week 11). Those are what make this project senior-level evidence.

## Weekly log (copy per week)

```
### Week N: <theme>
- Done:
- Blocked / surprises:
- Numbers (before -> after):
- ADR written:
- DDIA read:  Xu read:
```