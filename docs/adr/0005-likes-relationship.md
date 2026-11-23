# ADR 0005: Model likes as an idempotent user-to-post relationship

- **Status:** Accepted; backend API and persistence implemented in PR #16
- **Date:** 2026-11-24

## Context

A user can like a post, unlike it, and read whether they have liked it along with the current like count. The relationship must remain unique under retries and concurrent requests. Like operations must also respect the same post visibility rules as reading a post.

A like count could be stored directly on the post, but that introduces a second piece of mutable state that must remain synchronized with the underlying user/post relationships.

## Decision

### 1. Store likes as relationship rows

Use a dedicated PostgreSQL `post_likes` table with:

- `user_id` referencing `users.id`;
- `post_id` referencing `posts.id`;
- `created_at` recording when the relationship was created.

The composite primary key `(user_id, post_id)` is the uniqueness invariant. Both foreign keys cascade on hard deletion. Soft-deleting a post does not delete its likes; the post's visibility policy prevents those likes from being read through the API.

### 2. Use explicit idempotent operations, not a toggle

Expose:

- `GET /api/v1/posts/{post_id}/like` — read viewer state and count;
- `POST /api/v1/posts/{post_id}/like` — ensure the relationship exists;
- `DELETE /api/v1/posts/{post_id}/like` — ensure the relationship does not exist.

The PostgreSQL adapter uses `INSERT ... ON CONFLICT DO NOTHING` for like creation. Deleting a missing row is harmless. A toggle was rejected because retrying a request after a lost response could reverse the first successful operation.

### 3. Reuse post visibility authorization

Before reading or mutating a like, `LikeService` calls `PostService.get_post()`. The posts module remains the owner of post visibility policy, including deleted posts, inactive authors, private-account follow requirements, and blocks in either direction. The likes module does not duplicate these rules.

### 4. Derive the count from the relationship table

For this first implementation, PostgreSQL is the source of truth. The repository uses one aggregate query to return the viewer's `liked` state and `like_count`. No denormalized counter, cache, or event is written.

A stored counter would need a reliable atomic update and reconciliation strategy. Add one only after measurements show the aggregate query is a bottleneck and its consistency contract is designed.

### 5. Keep transaction ownership at the request boundary

The repository flushes changes through the request-scoped SQLAlchemy session. The request dependency owns commit/rollback. The database primary key, rather than a read-before-write check, protects uniqueness under concurrent requests.

## Alternatives considered

- **Boolean/counter column on posts:** rejected because it cannot represent which users liked a post and requires separate counter synchronization.
- **Toggle endpoint:** rejected because retries are not idempotent.
- **Read then insert:** rejected because concurrent requests can both observe the absence of a row.
- **Denormalized counter or Redis count:** deferred until measured read/write load justifies the extra consistency and repair work.
- **Emit notification/event immediately:** deferred until the project has a transactional outbox and an explicit event-delivery contract.

## Consequences

### Benefits

- Database-enforced uniqueness under concurrency.
- Retry-safe POST and DELETE semantics.
- Existing post visibility rules remain authoritative.
- Counts are derived from the source-of-truth relationship table.
- The API can return viewer state and count in one aggregate query.

### Costs and limitations

- Counting rows becomes more expensive as likes grow; no benchmark has yet established the threshold for denormalization.
- A count can change immediately after the response due to another user's concurrent action.
- The initial PR adds service-level unit tests, but PostgreSQL-backed API, migration, and concurrency tests remain required.
- Feed/profile response hydration and the React like control are not part of this ADR's implemented slice yet.
- Notifications and event streaming are not emitted by like mutations.

## Validation and follow-up

PR #16 added the migration, repository, service, authenticated routes, and unit tests for repeated like/unlike and visibility rejection.

Before treating likes as fully integrated product functionality:

1. Add PostgreSQL migration/API integration tests.
2. Add concurrent duplicate-like tests against the real unique constraint.
3. Include `like_count` and `is_liked_by_viewer` (or the agreed response shape) in feed/profile hydration using batched queries.
4. Add the frontend heart interaction with safe optimistic-update rollback.
5. Revisit counters and notifications only after the above behavior is stable.

## Revisit when

- Aggregate count latency is measured to be material.
- The product needs a paginated list of users who liked a post.
- Notifications or downstream analytics need reliable like events; introduce the outbox/event contract rather than publishing an event before the database transaction commits.
