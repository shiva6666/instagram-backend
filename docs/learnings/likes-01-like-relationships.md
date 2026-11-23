# Likes: a user-to-post relationship

This note explains the first likes implementation slice in `app/modules/likes/`.

## Product behavior

A signed-in user can read their like state, like a visible post, and unlike a visible post:

- `GET /api/v1/posts/{post_id}/like`
- `POST /api/v1/posts/{post_id}/like`
- `DELETE /api/v1/posts/{post_id}/like`

Each response contains `post_id`, `liked` (the current viewer's state), and `like_count`.

## Why a separate table?

A like is not a field on a post. It is a many-to-many relationship:

- one user can like many posts;
- one post can be liked by many users;
- one user can like a given post only once.

The `post_likes` table stores `user_id`, `post_id`, and `created_at`. The pair `(user_id, post_id)` is the primary key. That database constraint is the final guard against duplicate likes, even if two requests race or application code is bypassed.

Both foreign keys cascade on hard deletion of the related user or post. A normal post deletion in this project is a soft delete; its likes remain stored but are not exposed because the post visibility check rejects the deleted post.

## Why separate POST and DELETE instead of a toggle?

A toggle endpoint is ambiguous under retries. Imagine a client sends "toggle", the server succeeds, but the response is lost. Retrying the same request would undo the first action.

Explicit operations are naturally idempotent:

- POST means "ensure this user has liked this post". PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` makes repeats safe.
- DELETE means "ensure this user has not liked this post". Deleting an absent row is also safe.

This is easier to retry after network failures and easier to reason about than a toggle.

## Why does the service call PostService?

A like must not become a way to discover or interact with a post the viewer cannot see. The likes service delegates visibility authorization to the existing post service rather than copying rules for:

- missing or soft-deleted posts;
- inactive or deleted authors;
- private accounts and accepted-follow requirements;
- blocks in either direction;
- post visibility.

This keeps the posts module as the owner of post visibility policy. The likes module owns only the relationship mutation and its summary.

## Why derive the count instead of storing a counter?

For the first correct version, PostgreSQL is the source of truth and `like_count` is calculated from `post_likes`. A stored counter creates a second piece of state that must be updated atomically on every like/unlike and repaired if an update is missed or duplicated.

The repository reads the viewer's `liked` state and the count in one aggregate query, so both values come from the same statement snapshot. We can introduce a cached or denormalized counter later, after measuring the query cost and designing reconciliation.

## Transaction and concurrency boundaries

The authenticated request dependency owns the SQLAlchemy transaction: it commits after the route succeeds and rolls back if an exception escapes.

The unique composite primary key is the concurrency invariant. The repository uses PostgreSQL's conflict-safe insert instead of a read-then-insert sequence. A read-then-insert sequence would still have a race: two requests could both observe "not liked" before either inserts.

The returned count is a current database count, not a promise that it cannot change immediately after the response. Another user can like or unlike concurrently.

## Deliberately not included yet

- No notifications or event broker. A like currently commits only the relationship row.
- No materialized like counter.
- No paginated list of people who liked a post.
- No feed/profile response hydration for like summaries yet; that is the next integration slice for the frontend.
- PostgreSQL integration/concurrency tests are still required in addition to the service tests.

## Test cases in this slice

- Repeated like requests leave one relationship and return a count of one.
- Repeated unlike requests leave no relationship and a count of zero.
- A viewer who cannot see a post cannot like it or read its like state.

