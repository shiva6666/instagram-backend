# Engineering Roadmap: Instagram-Style Backend

A practical, learning-first plan for building the system in the repository's README blueprint. The goal is not to recreate Instagram's infrastructure immediately. The goal is to build a correct, testable modular monolith, measure its bottlenecks, and introduce distributed-system patterns only when the product needs them.

> **Guiding rule:** build a working vertical slice before adding infrastructure. PostgreSQL is the source of truth; caches and asynchronous projections must be rebuildable. Keep the target architecture aspirational until code, tests, and operational evidence exist.

## Product outcome

A user can register, authenticate, create a profile, follow other users, publish media-backed posts, and receive a useful feed. The system should then evolve to support asynchronous processing, hybrid feed fan-out, notifications, search, ranking, and scale experiments.

## How to use this roadmap

- Work in **milestones**, not calendar promises. A milestone may take longer than one week; correctness is more important than the schedule.
- Every milestone has a demonstrable outcome and exit criteria. Do not advance just because the checklist is mostly complete.
- Keep the modular monolith. Modules expose application/service interfaces; they do not import another module's ORM rows or domain internals.
- Prefer the simplest implementation that meets measured requirements. A technology appearing in the target diagram is not a requirement to add it now.
- Write an ADR when a decision has meaningful alternatives or long-term consequences. Record benchmarks before and after optimization.
- Update the **Current repository status** section and checkboxes only after verifying code and tests on the default branch.
- Use AI tools for review, test ideas, and boilerplate; understand and own the design and critical implementation.

## Current repository status (verified against the repository as of 2026-11-12)

| Area | Current state | Next action |
|---|---|---|
| FastAPI application and health route | Present; health/readiness smoke path exists | Keep dependency checks and smoke flows green |
| Core configuration and async SQLAlchemy setup | Present | Document and enforce transaction/session conventions across modules |
| PostgreSQL migrations | Present: users, posts, follows, auth identities, refresh tokens | Review schema constraints and indexes against actual query patterns |
| Users domain model, service, repository adapter | Present with profile APIs, status checks, and profile update behavior | Add more edge-case authorization and status tests |
| Authentication | Present: register/login/refresh/logout and authenticated `me` route, using Argon2id + JWT + opaque refresh tokens | Close remaining proof gaps: concurrency, reuse, invalid-token coverage, and secret-handling verification |
| Posts application module/API | Present: create/get/list-by-author/delete with owner checks and role/status gates | Hardening: visibility rules, cursor pagination, and broader PostgreSQL integration coverage |
| Follow graph API/service | Not implemented | Build after the auth/profile/post slice is stable |
| Feed | Not implemented | Start with a correct PostgreSQL chronological feed baseline |
| Media processing, event consumers, ranking | Not implemented | Defer until the synchronous product path is reliable |

This is a code-level snapshot, not a claim that every infrastructure container or roadmap experiment is complete. Re-check it when the roadmap changes.

## Improvement priorities (highest-leverage work)

These are the gaps that matter most before adding more product surface area:

- [ ] Align roadmap status to verified repository reality. Milestones should distinguish implemented, tested, and still-theoretical work.
- [ ] Close the auth proof gaps: concurrent refresh attempts, refresh-token reuse behavior, expired/invalid token handling, and secret/logging guardrails.
- [ ] Harden the post/profile slice with explicit visibility rules, stable pagination semantics, and PostgreSQL-backed edge-case tests.
- [ ] Make repo/service/router responsibilities explicit in docs and reviews: repositories persist data, services encode business rules, routers translate HTTP requests/responses.
- [ ] Add a lightweight quality gate for every milestone: unit tests, PostgreSQL integration tests, concurrency tests, benchmark evidence, and security review for auth flows.
- [ ] Keep the social graph and feed work behind a clean follow-up milestone once auth and docs are verified.

These improvements reduce the risk of building features on an unproven foundation and keep the roadmap honest about what is already working versus what is still aspirational.

## Delivery map

| Milestone | Focus | Deliverable |
|---|---|---|
| 0 | Foundation and engineering workflow | Reliable local development and CI |
| 1 | Authentication | Secure register/login/refresh/logout and protected route |
| 2 | Profiles and posts | Working user and post APIs with ownership rules |
| 3 | Social graph and baseline feed | Follow graph and cursor-paginated chronological feed |
| 4 | Media lifecycle | Presigned upload, validation, processing, and media delivery |
| 5 | Reliability and performance baseline | Tests, observability, query plans, reproducible load tests |
| 6 | Engagement and notifications | Likes/comments and asynchronous notification workflow |
| 7 | Feed scaling | Redis timeline and hybrid fan-out, measured against baseline |
| 8 | Search and ranking | Search index and explainable ranking v1 |
| 9 | Scale and resilience studies | Failure drills, capacity report, architecture evolution |

---

# Milestone 0 — Foundation and workflow

**Status:** Core scaffold exists. Verify each item before marking it complete.

### Build

- [x] Confirm one documented command starts the required local dependencies and API.
- [x] Confirm configuration is environment-driven; no secrets are committed.
- [ ] Confirm Alembic upgrade and downgrade work against a clean PostgreSQL database.
- [x] Define a consistent async SQLAlchemy session and transaction boundary convention.
- [x] Ensure application lifespan closes database and Redis resources reliably.
- [ ] Ensure readiness checks dependencies with bounded timeouts; liveness does not depend on them.
- [x] Keep Ruff, mypy, and pytest checks in CI; add PostgreSQL-backed integration tests.
- [x] Add a small smoke script that exercises the public API journey as features arrive.
- [x] Document local setup, migrations, tests, and common troubleshooting.

### Exit criteria

A new clone can be configured, start locally, apply migrations, pass CI, and answer health/readiness checks. A clean database can be migrated from zero.

---

# Milestone 1 — Authentication

**Status:** Password-based auth and an initial PostgreSQL-backed journey test are implemented. Rate limiting and the remaining proof items are still pending.

**Design baseline:** email/password authentication; Argon2id password hashes; short-lived signed JWT access tokens; high-entropy opaque refresh tokens stored only as hashes; refresh-token rotation; server-side revocation. OAuth/OIDC is a later extension, not part of the first login implementation.

### 1A. Design before coding

- [x] Decide the initial login identifier (email) and email normalization rules.
- [x] Define whether one user can have multiple auth identities and how future OIDC identities map to a user.
- [x] Design `auth_identities`: user FK, provider, normalized provider subject/identifier, password hash for the password provider, timestamps, and uniqueness constraints.
- [x] Design `refresh_tokens`: token hash, user/session family, created/expiry/consumed/revoked timestamps, and successor reference.
- [x] Define transaction ownership for registration so user + identity creation is atomic.
- [x] Decide client credential transport before finalizing API response/cookie behavior. Browser cookies require CSRF/origin protections; mobile clients need platform secure storage.
- [x] Write an ADR for access/refresh token choices, lifetimes, revocation, and client storage.

### 1B. Implement

- [x] Add `app/modules/auth/` with router, schemas, service, repository, token/security helpers, and dependencies.
- [x] Add an Alembic migration for auth identities and refresh-token sessions.
- [x] Implement Argon2id hash and verify; never store or log plaintext passwords.
- [x] Issue short-lived JWT access tokens with explicit issuer, audience, subject, issued-at, expiry, token ID, and a fixed allowed algorithm.
- [x] Validate signature, algorithm, issuer, audience, expiry, and required claims.
- [x] Implement opaque refresh tokens using cryptographically secure randomness; persist only a SHA-256 hash or keyed fingerprint.
- [x] Rotate refresh tokens atomically. Exactly one concurrent refresh may consume a token.
- [x] Define and implement refresh-token reuse handling (including family revocation) and document the concurrent-client trade-off.
- [x] Implement logout/revocation and `get_current_user`; resolve the active user/account state after token validation.
- [x] Keep authentication (who is calling?) separate from authorization (may they do this?).

### 1C. Prove it

- [x] Unit tests for password hashing, token claims/validation, and service behavior.
- [x] Integration tests for registration, duplicate identity, login, wrong password, expired access token, refresh rotation, logout, and revoked token.
- [ ] Concurrency test: two refresh attempts using the same token cannot both succeed.
- [ ] Reuse test: a consumed refresh token triggers the documented family policy.
- [ ] Verify secrets, passwords, access tokens, and refresh tokens never appear in logs.
- [x] Add a smoke flow for register → login → protected endpoint → refresh → logout.

### Exit criteria

A user can register and log in, access a protected endpoint, rotate a refresh token, and log out. Invalid, expired, revoked, and reused credentials are rejected. Security and concurrency tests pass.

**Deferred:** Google login, OIDC, MFA, password reset, device/session management UI, and advanced risk-based authentication. Revisit when the core identity lifecycle is stable.

---

# Milestone 2 — Profiles and posts

**Status:** The basic user profile and post modules are implemented in the codebase. Remaining work is mostly around hardening, visibility rules, pagination, and PostgreSQL-backed proof coverage.

### Profiles

- [x] Add user profile HTTP schemas and routes: get own profile, get public profile, update editable fields.
- [x] Define which fields are public and which are private; never expose internal/authentication fields.
- [x] Add profile update validation and updated-at behavior.
- [x] Add account status rules for active, suspended, and pending deletion.
- [x] Add tests for missing users, suspended users, and attempts to edit another user's profile.

### Posts

- [x] Create a posts module with domain model, repository port/adapter, service, schemas, and router.
- [x] Implement create, get, list-by-author, and soft-delete operations.
- [x] Enforce owner-only post mutation using the authenticated principal.
- [ ] Define post visibility and lifecycle states before media integration.
- [ ] Use cursor pagination for author post lists.
- [ ] Add database constraints and indexes justified by the actual query patterns.
- [ ] Add integration tests using PostgreSQL.

### Exit criteria

Authenticated users can manage their own profile and posts; other users cannot mutate them. API responses are typed, bounded, and tested. No business rules live in route handlers.

---

# Milestone 3 — Social graph and chronological feed

### Follow graph

- [ ] Add follow/unfollow service and endpoints.
- [ ] Make follow operations idempotent; enforce no self-follow and unique follower/followee pairs in PostgreSQL.
- [ ] Decide private-account follow request behavior and model pending vs accepted relationships.
- [ ] Add followers/following lists with cursor pagination.
- [ ] Add block semantics before feed visibility is considered complete.
- [ ] Test duplicate requests, unfollow, private profiles, blocks, and deleted/suspended accounts.

### Baseline feed

- [ ] Implement a PostgreSQL-only chronological feed from accepted follow relationships.
- [ ] Define feed visibility rules centrally: private account, block, deleted post, suspended author.
- [ ] Use keyset/cursor pagination with a stable tie-breaker; avoid offset pagination for the feed.
- [ ] Batch-hydrate post and author data; prevent N+1 queries.
- [ ] Test duplicate-free pagination while new posts are being created.
- [ ] Record `EXPLAIN (ANALYZE, BUFFERS)` plans and a reproducible baseline for realistic seeded data.

### Exit criteria

A user can follow accounts and retrieve a correct, private-aware, cursor-paginated chronological feed from PostgreSQL. Save p50/p95/p99 latency, throughput, dataset size, and query plans as the baseline for later optimization.

---

# Milestone 4 — Media lifecycle

Start with images. Add video only after the image path is reliable.

- [ ] Add a media module and media metadata table linked to owner and post.
- [ ] Generate short-lived presigned upload URLs; clients upload bytes directly to S3-compatible object storage (MinIO locally).
- [ ] Implement upload completion/finalization and verify the object exists.
- [ ] Validate size, allowed content types, and file signatures; never trust the filename or extension.
- [ ] Process images into bounded variants and thumbnails; strip sensitive EXIF metadata where appropriate.
- [ ] Track explicit states such as pending, processing, ready, and failed.
- [ ] Make processing retryable and idempotent; use immutable/versioned object keys.
- [ ] Ensure posts with media are not visible as ready until required processing succeeds.
- [ ] Define cleanup for abandoned uploads and deleted media.
- [ ] Add end-to-end tests for successful upload, invalid content, expired URL, retry, and worker failure.

### Exit criteria

A smoke script can create a post with an image, upload it directly to MinIO, complete processing, and retrieve the ready media. Failures are visible and recoverable.

**Deferred:** video transcoding, global CDN, multi-region object replication, and advanced image formats.

---

# Milestone 5 — Engineering quality and performance baseline

This milestone is a gate before introducing more distributed components.

- [ ] Add request IDs and structured logs; never log credentials or tokens.
- [ ] Add metrics for request rate, latency, errors, DB pool, and dependency failures.
- [ ] Add a basic dashboard and document how to run it locally.
- [ ] Add timeouts for database, Redis, and object-storage calls.
- [ ] Add CI integration tests against real PostgreSQL and Redis services.
- [ ] Add migration tests and verify clean install/upgrade paths.
- [ ] Seed realistic distributions (including skewed follower counts); record seed assumptions.
- [ ] Add load tests for login, post creation, profile, and feed read paths.
- [ ] Save benchmark commands, environment, dataset size, and p50/p95/p99 results.
- [ ] Fix measured slow queries and N+1 behavior before adding caches.
- [ ] Write a checkpoint retrospective and update architecture docs.

### Exit criteria

The core user journey is reproducible from a clean environment. CI is green. There is a trustworthy performance baseline and enough telemetry to explain where time is spent.

---

# Milestone 6 — Engagement and notifications

- [ ] Add likes with a unique user/post constraint and idempotent like/unlike behavior.
- [ ] Add comments with cursor pagination and moderation/deletion semantics.
- [ ] Add counters only after deciding whether they are authoritative or derived.
- [ ] Introduce an event contract with event ID, type, version, aggregate ID, occurred-at timestamp, and payload.
- [ ] Add an outbox table and write domain changes + outbox events in the same PostgreSQL transaction.
- [ ] Publish outbox events to Redpanda/Kafka-compatible broker via a restartable relay.
- [ ] Add idempotent consumers, bounded retries, dead-letter handling, and replay tooling.
- [ ] Build in-app notifications from follow/like/comment events.
- [ ] Track outbox backlog, consumer lag, retry count, and DLQ depth.
- [ ] Test duplicate delivery, consumer restart, poison messages, and broker downtime.

### Exit criteria

A broker outage does not lose committed domain events. Consumers can restart and replay safely. Duplicate events do not create duplicate likes, counters, or notifications.

**Important:** use at-least-once delivery plus idempotent consumers. Do not claim end-to-end exactly-once processing.

---

# Milestone 7 — Feed scaling and hybrid fan-out

Only begin after the PostgreSQL feed is correct and benchmarked.

### Redis timeline

- [ ] Treat PostgreSQL as source of truth and Redis timelines as disposable derived data.
- [ ] Add fan-out-on-write for ordinary accounts using Redis sorted sets.
- [ ] Consume a post-ready event; fan out in batches with bounded concurrency.
- [ ] Read timeline IDs from Redis and batch-hydrate/filter against PostgreSQL.
- [ ] Define cache/timeline retention, ordering, deduplication, and cursor semantics.
- [ ] Add a rebuild/backfill job and a timeline drift metric.
- [ ] Compare feed correctness and p95 latency against the PostgreSQL baseline.

### Hybrid strategy

- [ ] Add a configurable high-follower threshold based on measurements, not a hard-coded assumption.
- [ ] Keep high-follower authors on a pull/read-time candidate path.
- [ ] Merge pushed and pulled candidates; deduplicate, apply visibility rules, then rank.
- [ ] Handle follow/unfollow, block, private account, deletion, and threshold-crossing cases.
- [ ] Load test normal and high-follower authors; record write amplification and feed latency.
- [ ] Add repair tests that compare derived timelines with source-of-truth results.

### Exit criteria

The hybrid feed is correct under state changes and failures, Redis can be rebuilt, and benchmarks show the trade-offs versus the baseline.

---

# Milestone 8 — Search and ranking v1

### Search

- [ ] Start with PostgreSQL full-text search for users and captions/hashtags where suitable.
- [ ] Measure query quality and latency before adding a separate search engine.
- [ ] If evidence justifies it, add OpenSearch as a derived index fed by events.
- [ ] Implement reindex-from-source and deletion/visibility propagation.
- [ ] Expose and measure indexing lag.

### Ranking

- [ ] Keep chronological feed as a reliable fallback.
- [ ] Implement explainable score v1 using recency and simple engagement/affinity features.
- [ ] Separate candidate generation, filtering, scoring, and hydration.
- [ ] Put ranking behind a feature flag and use stable user bucketing.
- [ ] Evaluate offline against a documented dataset; do not equate engagement with user value.
- [ ] Add abuse/spam signals and moderation policy hooks before optimizing purely for engagement.

### Exit criteria

Search can be rebuilt from source-of-truth data. Ranking can be disabled safely and falls back to chronological delivery. Quality and latency are measured.

---

# Milestone 9 — Scale, resilience, and advanced studies

Pick experiments based on bottlenecks and learning goals. These are not prerequisites for the core product.

- [ ] Failure drills: Redis unavailable, broker unavailable, worker crash, poison event, object storage unavailable.
- [ ] Graceful worker shutdown, retry with backoff/jitter, dead-letter inspection and replay.
- [ ] Backup/restore PostgreSQL and document recovery objectives.
- [ ] Define service-level indicators/objectives for API availability, feed latency, and notification delay.
- [ ] Capacity test at increasing load; identify the first bottleneck with evidence.
- [ ] Study Postgres read replicas and consistency trade-offs; implement a replica only for a concrete experiment.
- [ ] Study partitioning and sharding; prototype only after a measured single-node limit.
- [ ] Study CDN behavior with immutable media URLs and cache headers.
- [ ] Add stories, real-time delivery, recommendation/embedding experiments, or video processing only when the core journey is stable.
- [ ] Write a final architecture review: what is implemented, what is simulated, what would change at 10x/100x, and why.

### Exit criteria

A reproducible capacity report, failure-drill notes, recovery instructions, current ADRs, and an honest architecture diagram distinguish implemented components from future concepts.

---

## Technology policy: default choices, not a shopping list

| Concern | Start with | Add only when justified |
|---|---|---|
| Primary data | PostgreSQL | Read replicas, partitioning, sharding |
| Cache / timeline | Redis | Cluster/sharding after measured limits |
| Media bytes | S3-compatible object storage (MinIO locally) | CDN, multi-region storage |
| Async work | Simple in-process/background worker for early experiments | Redpanda/Kafka + outbox when durability/fan-out requires it |
| Search | PostgreSQL full-text search | OpenSearch when query/load needs it |
| Feed | PostgreSQL chronological query | Redis fan-out and hybrid candidate generation |
| Ranking | Chronological, then explainable rules | Feature store and ML when evaluation data exists |
| Observability | Structured logs + basic metrics | Tracing, dashboards, alerting as complexity grows |

Do not introduce Cassandra, Kubernetes, microservices, a service mesh, or multi-region deployment just because they appear in a large-scale reference diagram. Study them, document the trade-offs, and build a small experiment only when there is a clear learning objective.

## Backend quality bar (every milestone)

- [x] Routes validate input/output and delegate business logic to application services.
- [x] Domain models, HTTP schemas, and ORM rows have distinct responsibilities.
- [ ] Module boundaries are explicit; no cross-module ORM-row imports.
- [x] Database constraints protect invariants that must survive concurrent requests.
- [x] Mutating operations have documented transaction boundaries.
- [ ] Pagination is bounded and uses a stable cursor where collections can grow.
- [ ] Authorization is enforced on every resource operation; do not trust client-supplied owner IDs.
- [ ] Background work is idempotent, observable, retryable, and bounded.
- [ ] Secrets and credentials never enter logs, traces, fixtures, or committed config.
- [ ] Tests cover success, failure, authorization, concurrency, and relevant state transitions.
- [ ] Every performance claim has a reproducible measurement.

## Documentation and evidence checklist

- [x] README accurately describes implemented functionality and links to this roadmap.
- [x] Target architecture and implemented architecture are clearly distinguished.
- [ ] ADRs record meaningful decisions and are kept current.
- [x] Learning notes explain concepts and why the project chose a particular approach.
- [ ] Benchmarks include setup, dataset, command, and before/after results.
- [ ] Failure drills include symptom, trigger, impact, recovery, and follow-up action.

## Immediate next task: close the auth proof gaps and harden the profile/post slice

The current codebase already contains the first-pass auth and profile/post implementations. The next work is not a blank-slate design exercise; it is to close the remaining proof and hardening gaps:

1. Finish the auth test matrix: unit coverage, invalid/expired token cases, token reuse, concurrent refresh behavior, and secret-handling checks.
2. Verify the existing registration/login/refresh/logout flow against PostgreSQL under real CI conditions and fix any failing edge cases.
3. Harden the profile and post module with explicit visibility rules, ownership enforcement, and edge-case tests (suspended accounts, private profiles, user-not-found, and unauthorized mutations).
4. Decide whether to keep the current offset-based author listing or move to a stable cursor strategy before the feed layer is introduced.
5. Only then move to the follow graph and feed baseline work in Milestones 3 and beyond.

**Definition of done for the next task:** a verified, green auth/profile/post slice with documented remaining risks and a clear path into the follow/feed milestones.

## Weekly / milestone log template

Copy this entry when closing a milestone:

```markdown
### Milestone: <name>
- Delivered:
- Tests and evidence:
- Benchmark (environment / dataset / p50 / p95 / p99):
- ADRs or docs updated:
- Trade-offs and surprises:
- Deferred work:
- Next milestone:
```
