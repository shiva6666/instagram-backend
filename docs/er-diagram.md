# Instagram-style ER diagram

The relationships below model the PostgreSQL source of truth. Feed timelines
and notification delivery can be materialized in Redis, but the relational
tables remain authoritative.

# Instagram-style ER diagram

PostgreSQL is the source of truth. Redis timelines, counters, and
notification delivery are derived projections, fed by `OUTBOX_EVENTS`.

```mermaid
erDiagram
    USERS {
        uuid id PK "UUIDv7"
        citext username UK
        citext email UK
        text bio
        varchar avatar_key
        boolean is_private
        varchar status "active | suspended | pending_deletion"
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at "nullable"
    }

    AUTH_IDENTITIES {
        uuid id PK
        uuid user_id FK
        varchar provider "password | google"
        varchar provider_subject
        text secret_hash "nullable"
        timestamptz secret_changed_at
        timestamptz created_at
    }

    REFRESH_TOKENS {
        uuid id PK
        uuid user_id FK
        uuid family_id "rotation chain"
        char token_hash UK "sha256, never raw"
        uuid replaced_by_id FK "nullable"
        varchar user_agent
        timestamptz expires_at
        timestamptz revoked_at "nullable"
        timestamptz created_at
    }

    USER_STATS {
        uuid user_id PK, FK
        int follower_count
        int following_count
        int post_count
        timestamptz updated_at
    }

    POSTS {
        uuid id PK "UUIDv7"
        uuid user_id FK
        text caption
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at "nullable"
    }

    POST_STATS {
        uuid post_id PK, FK
        int like_count
        int comment_count
        timestamptz updated_at
    }

    MEDIA {
        uuid id PK
        uuid post_id FK
        varchar media_type "image | video"
        varchar status "pending | processing | ready | failed"
        text storage_key "original upload"
        varchar mime_type
        bigint size_bytes
        char checksum_sha256
        int width
        int height
        int duration_ms "video only"
        varchar blurhash "placeholder"
        smallint position
        timestamptz created_at
    }

    MEDIA_VARIANTS {
        uuid media_id PK, FK
        varchar variant PK "thumb | feed | full"
        text storage_key
        int width
        int height
    }

    FOLLOWS {
        uuid follower_id PK, FK
        uuid following_id PK, FK
        varchar status "pending | accepted"
        timestamptz created_at
    }

    BLOCKS {
        uuid blocker_id PK, FK
        uuid blocked_id PK, FK
        timestamptz created_at
    }

    LIKES {
        uuid user_id PK, FK
        uuid post_id PK, FK
        timestamptz created_at
    }

    COMMENTS {
        uuid id PK "UUIDv7"
        uuid post_id FK
        uuid user_id FK
        uuid parent_comment_id FK "nullable"
        text body
        timestamptz created_at
        timestamptz deleted_at "nullable"
    }

    NOTIFICATIONS {
        uuid id PK "UUIDv7"
        uuid recipient_id FK
        uuid actor_id FK
        uuid post_id FK "nullable"
        uuid comment_id FK "nullable"
        varchar type "follow | like | comment"
        timestamptz read_at "nullable"
        timestamptz created_at
    }

    OUTBOX_EVENTS {
        uuid id PK "UUIDv7"
        varchar aggregate_type
        uuid aggregate_id
        varchar event_type
        jsonb payload
        timestamptz created_at
        timestamptz published_at "nullable"
    }

    IDEMPOTENCY_KEYS {
        uuid user_id PK, FK
        varchar key PK
        char request_hash
        int response_status
        jsonb response_body
        timestamptz created_at
        timestamptz expires_at
    }

    USERS ||--o{ AUTH_IDENTITIES : "signs in with"
    USERS ||--o{ REFRESH_TOKENS : "has sessions"
    REFRESH_TOKENS o|--o| REFRESH_TOKENS : "rotates to"
    USERS ||--|| USER_STATS : has
    USERS ||--o{ POSTS : creates
    POSTS ||--|| POST_STATS : has
    POSTS ||--o{ MEDIA : contains
    MEDIA ||--o{ MEDIA_VARIANTS : "rendered as"
    USERS ||--o{ FOLLOWS : "follows (follower_id)"
    USERS ||--o{ FOLLOWS : "followed by (following_id)"
    USERS ||--o{ BLOCKS : "blocks (blocker_id)"
    USERS ||--o{ BLOCKS : "blocked by (blocked_id)"
    USERS ||--o{ LIKES : gives
    POSTS ||--o{ LIKES : receives
    USERS ||--o{ COMMENTS : writes
    POSTS ||--o{ COMMENTS : has
    COMMENTS |o--o{ COMMENTS : "replies to"
    USERS ||--o{ NOTIFICATIONS : "receives (recipient_id)"
    USERS ||--o{ NOTIFICATIONS : "triggers (actor_id)"
    POSTS |o--o{ NOTIFICATIONS : about
    COMMENTS |o--o{ NOTIFICATIONS : about
    USERS ||--o{ IDEMPOTENCY_KEYS : owns
```

`OUTBOX_EVENTS` has no relationship lines on purpose: events must outlive
the rows they describe.

## Scale-aware design notes

- `FOLLOWS`, `LIKES`, and `COMMENTS` are high-write tables. Use composite
  primary keys for follows and likes to prevent duplicates.
- Add these uniqueness and integrity rules:
  - `AUTH_IDENTITIES(provider, provider_subject) UNIQUE`.
  - `MEDIA(post_id, position) UNIQUE`.
  - `follower_id <> following_id` and `blocker_id <> blocked_id`.
  - `NOTIFICATIONS.type` must agree with its nullable `post_id` and
    `comment_id` references: likes require a post, comments require a
    comment, and follows require neither. A comment notification may also
    carry its post ID for efficient navigation.
- Add indexes for `posts(user_id, created_at, id)`,
  `posts(created_at, id)`, `follows(following_id, created_at)`,
  `follows(follower_id, created_at)`, `likes(post_id, created_at)`,
  `comments(post_id, created_at)`, `notifications(recipient_id, created_at)`,
  `outbox_events(published_at, created_at)`, and
  `refresh_tokens(user_id, revoked_at, expires_at)`.
- `REFRESH_TOKENS.replaced_by_id` references `REFRESH_TOKENS(id)` to model
  refresh-token rotation.
- The estimate of 4M posts/day and approximately 2 TB/day of media means
  `MEDIA` should store object-storage keys and metadata. Store image/video
  bytes in object storage, not PostgreSQL.
- The 200M feed reads/day estimate favors a Redis timeline containing bounded
  post IDs. Keep the full post, media, and interaction data in PostgreSQL or
  other durable stores.
- The Redis estimate should distinguish active users from all users. With
  20M active users, 500 entries, and 64 raw bytes per entry, the raw estimate
  is about 640 GB; with all 100M users it is about 3.2 TB. Sorted-set/list
  overhead, replication, and fragmentation must be added to either figure.
- Notifications should be written asynchronously from likes, comments, and
  follows. For celebrity accounts, avoid synchronously expanding a post to
  every follower; use hybrid fanout-on-write and fanout-on-read.
- At the estimated scale, partition or archive time-heavy tables such as
  `POSTS`, `COMMENTS`, `LIKES`, and `NOTIFICATIONS` by time after measuring
  query patterns. Retain `OUTBOX_EVENTS`, `IDEMPOTENCY_KEYS`,
  `NOTIFICATIONS`, and expired/revoked `REFRESH_TOKENS` only for their
  required operational or audit windows, then archive or delete them.

## Recommended SQL constraints

```sql
CREATE UNIQUE INDEX auth_identities_provider_subject_uq
    ON auth_identities (provider, provider_subject);

CREATE UNIQUE INDEX media_post_position_uq
    ON media (post_id, position);

ALTER TABLE refresh_tokens
    ADD CONSTRAINT refresh_tokens_replaced_by_fk
    FOREIGN KEY (replaced_by_id) REFERENCES refresh_tokens (id);

ALTER TABLE follows
    ADD CONSTRAINT follows_no_self_follow
    CHECK (follower_id <> following_id);

ALTER TABLE blocks
    ADD CONSTRAINT blocks_no_self_block
    CHECK (blocker_id <> blocked_id);

ALTER TABLE notifications
    ADD CONSTRAINT notifications_reference_check
    CHECK (
        (type = 'like' AND post_id IS NOT NULL AND comment_id IS NULL)
        OR (type = 'comment' AND comment_id IS NOT NULL)
        OR (type = 'follow' AND post_id IS NULL AND comment_id IS NULL)
    );
```
