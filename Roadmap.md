# Roadmap: Instagram-Style Modular Monolith (24 Weeks)

A task-by-task plan for building a modular FastAPI monolith (backend only; the frontend is deliberately out of scope), learning alongside *Designing Data-Intensive Applications* (DDIA) and Alex Xu's *System Design Interview* (Vol 1, Vol 2 where noted).

**Start date:** ____ **Target finish:** ____ (about 6 months)

## Progress overview

| Phase | Week | Theme | Status |
|---|---|---|---|
| Setup | 0 | Repo, Compose, CI | [ ] |
| 1: Foundations | 1 | Estimation + data model | [ ] |
| | 2 | Auth, users, posts | [ ] |
| | 3 | Follow graph + naive feed (baseline) | [ ] |
| | 4 | Postgres depth: indexes, plans, pooling | [ ] |
| | 5 | Media upload pipeline | [ ] |
| | 6 | **Checkpoint 1:** hardening, tests, metrics, retro | [ ] |
| 2: Fast and consistent | 7 | Fan-out on write, Redis timelines | [ ] |
| | 8 | Hybrid fan-out for celebrities | [ ] |
| | 9 | Timeline correctness and repair | [ ] |
| | 10 | Replication, read-your-writes | [ ] |
| | 11 | Transactions, counters, idempotency | [ ] |
| | 12 | **Checkpoint 2:** rate limiting, consistent hashing, retro | [ ] |
| 3: Events and resilience | 13 | Event bus and transactional outbox | [ ] |
| | 14 | Consumers in depth | [ ] |
| | 15 | Notifications and counters via events | [ ] |
| | 16 | Failure drills | [ ] |
| | 17 | Partitioning and sharding Postgres | [ ] |
| | 18 | **Checkpoint 3:** consolidation and retro | [ ] |
| 4: Breadth | 19 | Stories | [ ] |
| | 20 | Search | [ ] |
| | 21 | Media delivery and caching (CDN simulation) | [ ] |
| | 22 | Ranking v1 and engagement pipeline | [ ] |
| | 23 | GenAI features | [ ] |
| | 24 | Capacity test, hardening, packaging | [ ] |

## How to use this roadmap

- Each week has **Goal, Tasks, Tools, Read, and Exit criteria**. Do not start the next week until the exit criteria are met.
- **Pace:** about 10 to 12 hours per week: 2 to 3 build sessions, 1 DDIA session, 1 Xu session, and a weekend slot to break something, measure it, and write an ADR. If your weeks get shorter, keep the rhythm and let a module take two weeks.
- **Checkpoint weeks (6, 12, 18) are buffers.** Use them to catch up; do not compress earlier weeks to save time.
- **ADR** = one-page Architecture Decision Record in `docs/adr/`: context, options, decision, numbers, consequences.
- Write the core of every phase by hand. Use Claude Code as reviewer, test writer, and boilerplate generator, not as the author of the hard parts.
- Measure before and after every optimization. Save results in `docs/benchmarks/`.

## Reading schedule (DDIA 1st edition chapters; map by topic if you have the 2nd edition)

| Weeks | DDIA | Xu |
|---|---|---|
| 1 | Ch 1 Reliable, scalable, maintainable; Ch 2 Data models | Vol 1: scale from zero, estimation, unique ID generator |
| 2 | Ch 4 Encoding and evolution | |
| 3 to 4 | Ch 3 Storage and retrieval | |
| 7 to 8 | skim Ch 5 intro | Vol 1: news feed |
| 9 to 10 | Ch 5 Replication | |
| 11 | Ch 7 Transactions | |
| 12 | Ch 6 Partitioning | Vol 1: rate limiter, consistent hashing |
| 13 to 14 | Ch 11 Stream processing | Vol 1: distributed message queue concepts |
| 15 to 16 | Ch 8 Trouble with distributed systems | Vol 1: notification system |
| 17 to 18 | Ch 6 revisit, Ch 9 Consistency and consensus | |
| 20 | | Vol 1: search autocomplete |
| 22 | Ch 10 Batch processing | |
| 24 | Ch 12 Future of data systems | |

## Scope: what we build vs. what we only study

**Build:** auth, profiles, posts with media, follow graph, likes/comments, hybrid fan-out feed, cursor pagination, Redis timelines and counters, event bus and outbox, async workers, notifications, rate limiting, partitioning and a shard-router experiment, stories, search, CDN-style caching, ranking v1, GenAI features (embeddings, captions, moderation), observability, load tests.

**Study only (from the system design diagram):** DNS/GeoDNS, WAF/DDoS, multi-region replication, Cassandra, video transcoding, full ML training and model serving.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language / tooling | Python 3.12, `uv`, Ruff, mypy, pre-commit | Fast, typed, lint-clean from day 1 |
| API | FastAPI, Pydantic v2, Uvicorn/Gunicorn | Typed request/response models (like Zod + TS) |
| ORM / DB access | SQLAlchemy 2.0 (async), asyncpg, Alembic | Real migrations, explicit queries |
| Primary DB | PostgreSQL 16, PgBouncer, pgvector | Source of truth, pooling, embeddings |
| Cache / timelines | Redis 7 (sorted sets, hashes, Lua) | Timelines, counters, rate limits, features |
| Object storage | MinIO (S3-compatible), aioboto3 | Presigned uploads |
| Edge simulation | nginx caching proxy | CDN behavior locally |
| Event bus | Redpanda (Kafka API), aiokafka | Simple local Kafka |
| Search | Postgres FTS, then OpenSearch | Compare both with numbers |
| Analytics | DuckDB or pandas | Batch features and offline evaluation |
| Image processing | Pillow | Resize, thumbnails, EXIF strip |
| GenAI | LLM API of your choice, embedding model | Captions, moderation, semantic search |
| Auth | JWT (access + refresh), argon2 hashing | Standard, interview-friendly |
| Testing | pytest, pytest-asyncio, httpx, Testcontainers, Hypothesis | Real DBs in tests, property tests |
| Observability | structlog, Prometheus, Grafana, OpenTelemetry (optional) | Metrics and logs |
| Load testing | Locust or k6 | Before/after numbers |
| API exercising | `httpx` smoke scripts, Bruno or Hoppscotch, Swagger UI | Drive and demo the API without a UI |
| Contract testing | Schemathesis (optional), pytest e2e suite against Compose | Fuzz and verify the API from its OpenAPI spec |
| Infra / CI | Docker Compose, GitHub Actions | Reproducible dev and CI |

## Target repo layout

```
repo/
  app/
    core/            # config, db, redis, security, logging
    modules/
      auth/  users/  posts/  media/  graph/  feed/
      engagement/  notifications/  stories/  search/  ranking/  ai/
    workers/         # fanout, media, notifications, search-indexer, moderation
    main.py
  migrations/  tests/
  scripts/           # smoke.py, seed helpers, load-test scenarios
  infra/             # compose files, grafana dashboards, prometheus.yml, nginx
  docs/
    adr/  benchmarks/  drills/  estimation.md  architecture.md
  Makefile
  Roadmap.md
```

Rule: modules talk to each other through a small `service.py` interface only, never by importing another module's models directly. This keeps the monolith splittable later.

---

## Week 0: Setup (2 to 3 days, before Week 1)

**Goal:** a repo where one command starts everything.

- [ ] Repo layout with `app/`, `infra/`, `docs/`, `scripts/` (backend-only repo)
- [x] `docker-compose.yml` with Postgres, Redis, MinIO, Redpanda, pgAdmin, Prometheus, Grafana
- [x] Add FastAPI, SQLAlchemy, asyncpg, Alembic, pydantic-settings, structlog
- [x] Config via `pydantic-settings` (`.env`, no hardcoded secrets)
- [x] `/health` and `/ready` endpoints (ready checks Postgres + Redis)
- [x] Ruff + mypy (strict on `app/core`) + pre-commit hooks
- [x] GitHub Actions: lint, type-check, test on every PR
- [x] `Makefile`: `make up`, `make test`, `make migrate`, `make seed`
- [ ] `scripts/smoke.py` (httpx) that walks the main user journey; extend it each week
- [x] Create `docs/estimation.md` and `docs/adr/0001-modular-monolith.md`

**Exit criteria:** `make up` boots all services; CI is green on an empty test.

---

# Phase 1: Foundations (Weeks 1 to 6)

## Week 1: Estimation and data model

**Goal:** design before code, with numbers.

**Read:** DDIA: reliability/scalability/maintainability, data models and query languages. Xu Vol 1: *Scale From Zero to Millions*, *Back-of-the-Envelope Estimation*.

- [x] Write `docs/estimation.md`: DAU, posts/day, avg followers, read:write ratio, storage/year, peak QPS, timeline memory in Redis
- [x] Draw ER diagram: users, posts, media, follows, likes, comments, notifications
- [x ] Write Alembic migration 001 (users, posts, follows) with proper constraints and FKs
- [x] Decide ID strategy (UUIDv7 or snowflake-style) and write an ADR (links to Xu *Unique ID Generator*)
- [x] Add indexes you can justify: `posts(user_id, created_at, id)`, `follows(follower_id, created_at)`, and `follows(following_id, created_at)`
- [x] Add integrity constraints: unique auth provider identity, no self-follow/block, unique media position, and notification reference checks
- [x] Write a seed script (Faker): 10k users, 1M posts, power-law follower counts
- [x] Repository + service pattern for `users` module with unit tests

**Tools:** Alembic, SQLAlchemy, Faker, dbdiagram.io or Mermaid, pgAdmin.

**Exit criteria:** estimation doc re-reviewed after 24 hours (fix mistakes); seed script loads 1M posts in under 10 minutes.

## Week 2: Auth, users, posts CRUD

**Read:** DDIA: encoding and evolution (schema evolution, forward/backward compatibility).

- [ ] Register, login, refresh, logout endpoints (`AUTH_IDENTITIES`, Argon2 hashing, JWT access + refresh rotation through `REFRESH_TOKENS`)
- [ ] Auth dependency (`get_current_user`) and owner-only permission checks
- [ ] User profile GET/PATCH, avatar placeholder field
- [ ] Posts: create, get, delete (soft delete), list by author
- [ ] Pydantic request/response schemas separate from ORM models
- [ ] Consistent error format (RFC 7807-style problem details) and global exception handlers
- [ ] Request ID middleware + structured logs with request id and user id
- [ ] Integration tests with Testcontainers (real Postgres)
- [ ] Smoke script / Bruno collection for auth: register, login, refresh rotation, expired-token and reused-refresh-token cases

**Tools:** FastAPI dependencies, argon2-cffi, PyJWT, Testcontainers, httpx, Bruno or Hoppscotch.

**Exit criteria:** can register, log in, create a post via the smoke script; 80%+ coverage on auth and posts services.

## Week 3: Follow graph and the naive feed (your baseline)

**Read:** DDIA: storage and retrieval (B-trees vs LSM-trees, indexes).

- [ ] Follow/unfollow endpoints (idempotent, unique constraint, no self-follow)
- [ ] Followers/following lists with **cursor pagination** (keyset on `(created_at, id)`)
- [ ] Naive feed query: posts from followed users, ordered by time, via JOIN
- [ ] `EXPLAIN (ANALYZE, BUFFERS)` on every query; record plans in `docs/benchmarks/week3.md`
- [ ] Load test with Locust: 100 concurrent users reading feeds; record p50/p95/p99 and QPS
- [ ] Compare OFFSET vs keyset pagination at deep pages and document it
- [ ] Feed contract: response carries `items` + `next_cursor`; a script walks 50 pages and asserts no duplicates or gaps while new posts arrive

**Tools:** Postgres EXPLAIN, Locust or k6, `pg_stat_statements`.

**Exit criteria:** a saved baseline (e.g. "naive feed p95 = X ms at Y QPS with 1M posts"). Every later optimization is measured against this number.

## Week 4: Postgres depth (indexes, plans, pooling)

**Goal:** understand why your queries are fast or slow, not just that they are.

**Read:** DDIA Ch 3 (storage and retrieval) in full: B-trees, LSM-trees, write-ahead log, indexes. Postgres docs: indexes, `EXPLAIN`, MVCC.

- [ ] Scale the seed data to 10M posts; re-record the Week 3 baseline at this size
- [ ] Compare index types on the same query: plain B-tree, partial, covering (`INCLUDE`), BRIN on `created_at`; save plans and sizes
- [ ] Find and fix one sequential scan and one bad join order using `EXPLAIN (ANALYZE, BUFFERS)`
- [ ] Turn on `pg_stat_statements` and `auto_explain`; list your top 10 queries by total time
- [ ] Observe MVCC: bulk-update rows, watch table bloat and dead tuples, run `VACUUM`, read autovacuum settings
- [ ] Add PgBouncer to Compose; load test with and without it and record connection counts
- [ ] Write `docs/query-review-checklist.md` (index justified, plan saved, no N+1, bounded result size)
- [ ] ADR: index strategy for posts and follows, with measured sizes and write cost

**Tools:** `pg_stat_statements`, `auto_explain`, `pgbench`, PgBouncer, `pgstattuple` (optional).

**Exit criteria:** every hot query has a saved plan and a written reason for its index.
## Week 5: Media upload pipeline (synchronous version)

**Read:** Xu Vol 1: object storage / queue concepts; review your DDIA notes from Phase 1.

- [ ] `media` module: request presigned PUT URL, client uploads straight to MinIO
- [ ] `POST /media/complete` marks upload done and creates a `processing` media row
- [ ] Pillow worker (in-process for now): resize to 3 widths, WebP output, thumbnail, strip EXIF
- [ ] Post states: `PENDING_MEDIA` to `READY`; posts hidden from feeds until `READY`
- [ ] Validate content type, size limits, magic-bytes check (never trust the extension)
- [ ] Immutable, versioned object keys (`media/{id}/{variant}-{hash}.webp`)
- [ ] Upload smoke script: presign, PUT to MinIO, complete, poll the post until `READY`; cover expired URL and retry of `complete`
- [ ] ADR: why presigned uploads bypass the API server

**Tools:** MinIO, aioboto3, Pillow, `python-magic`, `httpx` for the upload script.

**Exit criteria:** end-to-end "create post with image" works from the smoke script, including the expired-URL case.

## Week 6: Checkpoint 1 (hardening, tests, metrics, retro)

**Goal:** make Phase 1 solid before building on it. This week is also your buffer: if you are behind, catch up here.

**Read:** DDIA Ch 1 revisit (reliability, scalability, maintainability); skim your own notes from Weeks 1 to 5.

- [ ] Fix the Week 0 findings if not done: `/ready` probe (broad catch + timeout), `get_session` as an async-generator dependency, lifespan `try/finally`
- [ ] CI runs integration tests with Postgres and Redis service containers; `mypy app` (strict on `app/core`)
- [ ] Coverage report in CI; raise the floor on auth, posts, graph, and media services
- [ ] Add `/metrics` with request rate, latency histograms, and error counts per route
- [ ] Grafana dashboard v1 (latency p50/p95/p99, error rate, DB pool usage)
- [ ] OpenAPI polish: response models, error schemas, examples on every route
- [ ] Optional: run Schemathesis against the OpenAPI spec and fix what it finds
- [ ] Extend `scripts/smoke.py` to cover the full Phase 1 journey
- [ ] Phase 1 retro in `docs/architecture.md`: what surprised you, what you would change, benchmark table so far

**Tools:** GitHub Actions service containers, `prometheus-fastapi-instrumentator`, Grafana, Schemathesis (optional).

**Exit criteria:** CI is green including integration tests; dashboard shows live latency for the smoke script.
---

# Phase 2: Fast and consistent (Weeks 7 to 12)

## Week 7: Fan-out on write with Redis timelines

**Read:** DDIA: replication (leaders and followers). Xu Vol 1: *Design a News Feed System*.

- [ ] Redis timeline per user: sorted set `timeline:{user_id}` (score = timestamp, member = post_id), capped at ~500 items initially; revise after benchmarks
- [ ] Fan-out worker: on post READY, fetch followers in batches, `ZADD` via pipeline
- [ ] Feed read path: `ZREVRANGEBYSCORE` for cursor, then hydrate posts from Postgres (batch fetch, no N+1)
- [ ] Post-hydration cache (Redis hash or JSON) with TTL and cache-aside
- [ ] Handle delete: remove from timelines or filter at hydrate time (document your choice in an ADR)
- [ ] Rebuild-timeline job for a user (needed for inactive users and recovery)
- [ ] Re-run the Week 3 load test; write `docs/benchmarks/week7.md` comparing against baseline

**Tools:** Redis sorted sets, redis-py asyncio, pipelines, Locust.

**Exit criteria:** feed p95 is at least 10x better than baseline, with a documented table.

## Week 8: Hybrid fan-out for celebrities

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

## Week 9: Timeline correctness and derived-data repair

**Goal:** a cache you cannot repair is a liability. Make Redis timelines provably consistent with Postgres.

**Read:** DDIA Ch 5 (replication) start, and the "derived data" ideas in Ch 11 intro.

- [ ] Define the truth: Postgres is the source; Redis timelines are derived and disposable
- [ ] Unfollow semantics: filter at read time via the follow graph, and clean up lazily
- [ ] Block and mute semantics; private and deleted posts hidden at hydrate time
- [ ] Backfill on follow: add the followee's last N posts to the follower's timeline
- [ ] Repair job: compare a user's Redis timeline with the Postgres truth, fix drift, report a drift metric
- [ ] Hypothesis stateful test: random sequences of post, follow, unfollow, delete; after repair, timeline equals the source-of-truth feed
- [ ] ADR: how derived data is rebuilt and how often

**Tools:** Hypothesis (stateful testing), Redis, pytest, Prometheus gauge for drift.

**Exit criteria:** the property-based test passes over thousands of random operation sequences.
## Week 10: Replication and read-your-writes

**Read:** DDIA: replication lag, read-your-writes, monotonic reads.

- [ ] Postgres streaming replica in Docker Compose
- [ ] Router: reads to replica, writes to primary, configurable per endpoint
- [ ] Inject artificial lag (`pg_wal_replay_pause` or network delay) and **reproduce a stale-read bug** (you post, refresh, post missing)
- [ ] Fix with read-your-writes: pin the author's reads to primary for N seconds after a write (or track LSN)
- [ ] Monotonic reads test: user does not see the feed go "back in time"
- [ ] API contract for clients: `POST /posts` returns the full hydrated post so any client can render it optimistically without re-reading from a lagging replica
- [ ] ADR: consistency guarantees per endpoint (feed vs profile vs post detail)

**Tools:** Postgres replication, `pg_stat_replication`, Toxiproxy (optional).

**Exit criteria:** a written test that fails without your fix and passes with it.

## Week 11: Transactions, counters, idempotency

**Read:** DDIA: transactions (isolation levels, write skew, lost updates). Xu Vol 1: *Design a Unique ID Generator* (revisit).

- [ ] Likes: unique `(user_id, post_id)` constraint; idempotent like/unlike
- [ ] Comments: create, list with cursor pagination, soft delete
- [ ] Denormalized counters (`like_count`) updated via Redis `INCR`, flushed to Postgres periodically
- [ ] **Reproduce a lost-update race** with concurrent requests, then fix (atomic SQL, `SELECT ... FOR UPDATE`, or Redis atomics)
- [ ] `Idempotency-Key` header on write endpoints (store key and response in Redis with TTL)

**Tools:** Postgres isolation levels, Redis Lua, pytest with `asyncio.gather` for race tests, Hypothesis.

**Exit criteria:** race tests reproduce the bug and prove the fix; counters stay correct under concurrent likes.

## Week 12: Checkpoint 2 (rate limiting, consistent hashing, retro)

**Goal:** protect the system, learn how data is spread across nodes, and consolidate Phase 2.

**Read:** DDIA Ch 6 (partitioning): key-range vs hash, hot spots, rebalancing. Xu Vol 1: *Design a Rate Limiter*, *Design Consistent Hashing*.

- [ ] Rate limiter v1: token bucket in Redis via a Lua script, per user and per IP
- [ ] Compare token bucket vs sliding window in a short experiment (burst behavior, memory per key)
- [ ] Return `429` with `Retry-After`; decide fail-open vs fail-closed per endpoint (ADR)
- [ ] Implement a consistent-hash ring with virtual nodes (script + unit tests)
- [ ] Use it to shard Redis timelines across 2 to 3 Redis instances in Compose (client-side sharding)
- [ ] Measure key movement when you add a node (expect about 1/N of keys) and compare with plain `hash % N`
- [ ] Re-run all Phase 2 benchmarks; update the baseline-vs-now table
- [ ] Phase 2 retro in `docs/architecture.md`; buffer time for anything unfinished

**Tools:** Redis Lua, Locust burst scenarios, a small hashing library you write yourself.

**Exit criteria:** adding a Redis node moves roughly 1/N of keys (measured); the rate limiter holds under a burst test.
---

# Phase 3: Events and resilience (Weeks 13 to 18)

## Week 13: Event bus and transactional outbox

**Goal:** move work off the request path without losing events.

**Read:** DDIA Ch 11 (stream processing): logs, brokers, change data capture. Xu Vol 1: *Design a Distributed Message Queue* concepts.

- [ ] Event schemas (Pydantic models) with `event_id`, `type`, `version`, `occurred_at`, `payload`
- [ ] **Transactional outbox:** write the event to an `outbox` table in the same DB transaction; a relay publishes to Redpanda
- [ ] Relay correctness: ordered per aggregate, safe to restart, no duplicate publish storms
- [ ] Topics: `post.created`, `media.uploaded`, `media.processed`, `like.created`, `comment.created`, `follow.created`
- [ ] Choose partition keys deliberately (e.g. `author_id`) and document ordering guarantees
- [ ] Move fan-out and media processing from in-process to Kafka consumers (`aiokafka`, consumer groups)
- [ ] ADR: outbox vs dual write vs CDC, and what each can lose

**Tools:** Redpanda, aiokafka, `rpk` CLI, Redpanda Console.

**Exit criteria:** a post created during a Redpanda outage is published after it recovers, with nothing lost.
## Week 14: Consumers in depth (idempotency, retries, ordering, schema evolution)

**Goal:** make asynchronous processing boring and safe.

**Read:** DDIA Ch 11 continued (exactly-once myths, reprocessing), Ch 4 revisit (schema evolution).

- [ ] Idempotent consumers (processed-event table or naturally idempotent writes)
- [ ] Retry with exponential backoff and jitter; dead-letter topic after N failures; a DLQ inspection and replay script
- [ ] Poison-message test: one bad event must not block its partition forever
- [ ] Ordering experiments: what breaks when two events for the same post go to different partitions
- [ ] Rebalance experiment: add and remove consumers, observe duplicate processing and lag
- [ ] Event schema evolution: add an optional field, then a v2 event; old and new consumers keep working
- [ ] Consumer lag metric and alert rule
- [ ] ADR: at-least-once plus idempotency, and why you are not chasing exactly-once

**Tools:** aiokafka, Redpanda Console, Hypothesis for duplicate and reorder delivery tests.

**Exit criteria:** kill and restart a worker mid-stream with no lost or duplicated timeline entries; old consumers survive a v2 event.
## Week 15: Notifications and counters via events

**Read:** Xu Vol 1: *Design a Notification System*. DDIA: batch vs stream review.

- [ ] `notifications` table + inbox endpoints (list, mark read, unread count)
- [ ] Notification consumer: like/comment/follow events to in-app notifications
- [ ] Aggregate noisy events ("Alice and 12 others liked your post") with a time window
- [ ] Per-user preferences (mute types)
- [ ] Real-time delivery to the browser via SSE or WebSocket (pick one, write an ADR)
- [ ] Counter aggregation consumer: batch like/view counts into Redis then Postgres
- [ ] Stream tests: an httpx streaming test asserts the event arrives; handle client disconnects, heartbeats, and `Last-Event-ID` resume
- [ ] Stub a push-notification provider interface (no real FCM/APNs)

**Tools:** SSE (`sse-starlette`) or FastAPI WebSockets, Redis pub/sub, aiokafka.

**Exit criteria:** liking a post triggers a live notification within a couple of seconds, with idempotent processing.

## Week 16: Failure drills

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

## Week 17: Partitioning and sharding Postgres

**Goal:** know what changes when one database is no longer enough, without pretending you need it.

**Read:** DDIA Ch 6 revisit (secondary indexes, rebalancing, request routing).

- [ ] Native range partitioning of `posts` by month; prove partition pruning with `EXPLAIN`
- [ ] Retention: detach and drop an old partition instead of a giant `DELETE`
- [ ] Hash-partition `likes` by `post_id`; compare index size and insert rate
- [ ] Spin up a second Postgres in Compose and build a tiny shard router by `user_id`
- [ ] Hit the cross-shard problems on purpose: feed hydration across shards, global uniqueness, cross-shard transactions
- [ ] Write the analysis: what you gave up, what it would cost in production, and what you would try first (read replicas, caching, bigger box)
- [ ] ADR: when to shard, and the chosen shard key

**Tools:** Postgres declarative partitioning, a second Postgres container, pytest.

**Exit criteria:** pruning is visible in `EXPLAIN`; the shard router passes tests; the cross-shard write-up exists.
## Week 18: Checkpoint 3 (Phase 3 retro and consolidation)

**Goal:** consolidate events, resilience, and partitioning. Buffer week.

**Read:** DDIA Ch 9 (consistency and consensus) with your drill notes next to you.

- [ ] Re-run every benchmark and update the baseline-vs-now table
- [ ] Dashboards: consumer lag, DLQ depth, outbox backlog, replica lag, Redis latency
- [ ] Review all ADRs: status, consequences, anything now outdated
- [ ] Pay down the tech-debt list you kept since Week 6
- [ ] Redo two Xu designs from memory on paper (news feed, notification system) and compare with what you built
- [ ] Phase 3 retro in `docs/architecture.md`

**Exit criteria:** the benchmark table and ADR index are current; no known broken test or flaky drill.
---

# Phase 4: Breadth (Weeks 19 to 24)

## Week 19: Stories (ephemeral content)

**Goal:** build a feature whose data is meant to disappear.

**Read:** Xu notes on feed and storage; DDIA TTL and retention discussion in the storage chapters.

- [ ] Story model with a 24h expiry; media reuses the Week 5 pipeline
- [ ] Active-stories index per author in Redis with TTL; Postgres keeps the record for audit
- [ ] Story tray read path: followed users with active stories, unseen first
- [ ] Seen-state tracking (Redis set or bitmap, flushed to Postgres) and view counts via events
- [ ] Expiry worker plus storage cleanup (delete or tier media after expiry)
- [ ] Test clock skew and boundary cases (story expiring mid-request)
- [ ] ADR: TTL in Redis vs scheduled deletes vs partition drops

**Tools:** Redis TTL and sorted sets, Kafka consumers, pytest with frozen time.

**Exit criteria:** expired stories disappear from the tray within a bounded, measured delay; seen-state survives a Redis restart.
## Week 20: Search

**Goal:** a second system fed by events, with its own consistency story.

**Read:** Xu Vol 1: *Design a Search Autocomplete System*. DDIA on derived data and secondary indexes.

- [ ] Start with Postgres full-text search (`tsvector`, GIN) for users and hashtags; measure it
- [ ] Add OpenSearch to Compose; index users, posts, and hashtags from your events
- [ ] Reindex-from-scratch script, and a safe alias swap for zero-downtime reindexing
- [ ] Prefix autocomplete (edge n-grams or the completion suggester)
- [ ] Measure and expose search lag (time from write to searchable)
- [ ] Handle deletes and visibility changes in the index (private accounts, deleted posts)
- [ ] ADR: Postgres FTS vs OpenSearch, with numbers

**Tools:** Postgres FTS, OpenSearch, aiokafka consumer, Locust.

**Exit criteria:** new users and posts become searchable within a few seconds; a full reindex works from the source of truth.
## Week 21: Media delivery and caching (CDN simulation)

**Goal:** understand what a CDN does by building a small one.

**Read:** Xu Vol 2 notes on object storage; HTTP caching (`Cache-Control`, `ETag`, `Vary`).

- [ ] Put nginx in Compose as a caching proxy in front of MinIO (your "edge")
- [ ] Immutable versioned keys with long `Cache-Control`; short TTL for anything mutable
- [ ] Signed, expiring URLs for private content; test expiry and tampering
- [ ] Measure cache hit ratio and origin load with and without the edge
- [ ] Compare invalidation strategies: versioned URLs vs purge; document why the diagram prefers versioned keys
- [ ] Blur-hash or tiny placeholder generated at upload time
- [ ] Range requests and `ETag` handling verified with `curl`
- [ ] ADR: cache keys and invalidation

**Tools:** nginx, MinIO, `curl -v`, Locust, Prometheus (nginx exporter optional).

**Exit criteria:** you can show hit ratio and the origin-request reduction as numbers.
## Week 22: Ranking v1 and engagement pipeline

**Goal:** go from a chronological feed to a staged, measurable ranked feed, without needing a real ML platform.

**Read:** DDIA Ch 10 (batch processing). Xu Vol 1 news feed chapter revisited with ranking in mind.

- [ ] Engagement events (impression, like, dwell, share) flow through Kafka
- [ ] Stream aggregator computes simple features (post like rate, author affinity) into a Redis feature store
- [ ] Multi-stage feed: candidate generation (timeline plus celebrity pull) then filter then score then blend
- [ ] Scoring v1: weighted engagement with recency decay; weights in config
- [ ] Daily batch job (DuckDB or pandas over exported events) to refresh author-affinity features
- [ ] Offline evaluation script comparing chronological vs ranked on logged data
- [ ] Feature flag with stable per-user bucketing for ranked vs chronological
- [ ] ADR: what gets computed online vs offline

**Tools:** Kafka consumers, Redis hashes, DuckDB, feature flag via config, Locust.

**Exit criteria:** ranked feed sits behind a flag; offline evaluation produces a comparison table.
## Week 23: GenAI features

**Goal:** add AI features the way you would in production: async, observable, and failure tolerant.

**Read:** pgvector docs (HNSW vs IVFFlat); your LLM provider's docs on rate limits and structured output.

- [ ] Embed captions; store in Postgres with pgvector and an HNSW index
- [ ] "Similar posts" and semantic search endpoints; compare recall and latency against OpenSearch keyword search
- [ ] Async caption / alt-text suggestion worker (LLM API of your choice) with timeouts, retries, and a cache keyed by media hash
- [ ] LLM-based moderation worker that consumes `post.created` and emits a verdict event; flagged posts hidden and queued for review
- [ ] Treat user content as untrusted input: delimit it, validate structured output, never let it change instructions
- [ ] Golden evaluation set with accuracy numbers and a regression test that runs in CI (mocked) and on demand (live)
- [ ] Cost and latency metrics per call, budget cap, circuit breaker with graceful degradation when the API is down
- [ ] ADR: where AI sits on the request path (never on it) and why

**Tools:** pgvector, an embedding model (local `sentence-transformers` or API), an LLM API, Pydantic structured outputs, Prometheus.

**Exit criteria:** evaluation numbers are recorded; turning the LLM API off degrades features without breaking posting or the feed.
## Week 24: Capacity test, hardening, and packaging

**Goal:** prove the system against your own estimate, then make it presentable.

**Read:** DDIA Ch 12 (the future of data systems); revisit your Week 1 estimation doc.

- [ ] Load test at 1x, 5x, and 10x of your estimated peak; find the first bottleneck at each level and record it
- [ ] Define SLOs (feed p95, availability, notification delay) and write the alert rules
- [ ] Security pass: input limits, security headers, dependency audit (`pip-audit`), secrets scan, authz review on every route
- [ ] Backup and restore drill for Postgres and a rebuild-from-events drill for derived stores
- [ ] End-to-end pytest suite against Compose: register, post with image, follow, see in feed, like, notification, search
- [ ] README with architecture diagram, how to run, decisions index, benchmark highlights
- [ ] Final `docs/architecture.md`: what changes at 10x, 100x (sharding, Cassandra, CDN, multi-region)
- [ ] Two mock interviews: "Design Instagram" in 45 minutes, using this project as your evidence
- [ ] Short walkthrough video or blog post

**Tools:** Locust or k6, Prometheus alert rules, `pip-audit`, pytest.

**Exit criteria:** a stranger can clone, run `make up`, and see the app working; the capacity report names the bottleneck at each load level.
---

## Backend quality bar (apply every week)

- [ ] Every endpoint has a typed schema, an integration test, and a documented error case
- [ ] No business logic in routers; routers call services, services call repositories
- [ ] Every migration is reversible and tested on seeded data
- [ ] No N+1 queries (add a test helper that counts queries)
- [ ] Every background job is idempotent
- [ ] Every config value comes from the environment
- [ ] Logs are structured and contain a request or event id

## API contract bar (apply every week)

- [ ] OpenAPI is accurate: response models, status codes, and error schemas declared on every route
- [ ] One pagination contract (`items`, `next_cursor`) used everywhere, documented once
- [ ] Breaking changes go through `/api/v2` or an additive change, never a silent edit
- [ ] Every new endpoint is covered by the smoke script or the e2e suite

## Final deliverables checklist

- [ ] Working monolith running via Docker Compose, with a smoke script that proves the journey
- [ ] 15+ ADRs
- [ ] Estimation doc and architecture doc (v1 and final)
- [ ] Benchmark report (baseline vs optimized, plus 1x/5x/10x capacity test)
- [ ] 5 failure-drill write-ups
- [ ] Grafana dashboards and alert rules
- [ ] CI green with lint, types, unit, integration, e2e
- [ ] README and a short walkthrough video or blog post

## If you fall behind

**Use the checkpoint weeks (6, 12, 18) first.** Then cut, in this order: Week 21 extras (blur-hash, range requests), Week 22 batch job, Week 17 shard-router experiment, Week 15 push-provider stub, Schemathesis fuzzing.

**Never cut:** the baseline benchmark (Week 3), hybrid fan-out (Week 8), timeline repair (Week 9), the race-condition tests (Weeks 10 and 11), the outbox and idempotent consumers (Weeks 13 and 14), and the failure drills (Week 16). Those are what make this project senior-level evidence.

## Weekly log (copy per week)

```
### Week N: <theme>
- Done:
- Blocked / surprises:
- Numbers (before -> after):
- ADR written:
- DDIA read:  Xu read:
```
