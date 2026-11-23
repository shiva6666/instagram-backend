# PR #13 — Chunk 1: Media Domain Model & State Machine

> The `Media` dataclass and `MediaStatus` are the foundation everything else builds on. Read this first.

---

## Why a Dedicated Domain Model?

Before PR #13, images were just URL strings stored in a `post_images` table. There was no concept of an "image asset" in the domain — no lifecycle, no ownership, no processing state.

The PR introduces a **first-class domain entity** for a media asset. Just like `User` represents a user, `Media` represents an image that an owner uploaded, that the backend processed, and that can be attached to a post.

---

## The `Media` Dataclass

```python
@dataclass(frozen=True, slots=True)
class Media:
    id: UUID
    owner_id: UUID
    object_key: str | None
    url: str | None
    content_type: str | None
    size_bytes: int | None
    status: str
    width: int | None
    height: int | None
    created_at: datetime
    updated_at: datetime
    expected_size_bytes: int | None = None
    upload_expires_at: datetime | None = None
    display_object_key: str | None = None
    thumbnail_object_key: str | None = None
    cleanup_requested_at: datetime | None = None
    failure_reason: str | None = None
```

### Every Field Explained

| Field | Type | Populated When | Purpose |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | At creation | UUIDv7 — time-ordered, unguessable |
| `owner_id` | `UUID` | At creation | The user who initiated the upload — enforced for all operations |
| `object_key` | `str \| None` | At creation | Storage path of the **original** uploaded file, e.g. `original/{owner_id}/{media_id}/source`. `None` for legacy URL-backed records. |
| `url` | `str \| None` | Legacy only | For images that existed before the media lifecycle (old plain URLs). `None` for all new uploads. |
| `content_type` | `str \| None` | At creation | Declared by the client: `image/jpeg`, `image/png`, or `image/webp`. Validated against magic bytes during processing. |
| `size_bytes` | `int \| None` | After READY | Actual byte size of the uploaded original — set after HEAD verification during `complete_upload`. |
| `expected_size_bytes` | `int \| None` | At creation | Declared by the client at upload ticket time. Used to validate that the actual stored object matches what was promised. |
| `status` | `str` | Always | The current lifecycle state. See state machine below. |
| `width` | `int \| None` | After READY | Original image width in pixels — extracted by ImageMagick `identify`. |
| `height` | `int \| None` | After READY | Original image height in pixels — extracted by ImageMagick `identify`. |
| `upload_expires_at` | `datetime \| None` | At creation | When the presigned PUT URL expires (now + 15 min). Used by `complete_upload` to decide if a missing object is an error or an expired-URL failure. |
| `display_object_key` | `str \| None` | After READY | Storage path for the processed display image: `processed/{owner_id}/{media_id}/display.webp` |
| `thumbnail_object_key` | `str \| None` | After READY | Storage path for the thumbnail: `processed/{owner_id}/{media_id}/thumbnail.webp` |
| `cleanup_requested_at` | `datetime \| None` | On `discard()` | Timestamp when the owner requested deletion. The cleanup job picks this up and purges storage + DB row. |
| `failure_reason` | `str \| None` | On failure | Human-readable failure description, capped at 240 chars. E.g. `"animated images are not supported"`. |

### Why so many `None` fields?

Each field is progressively filled through the lifecycle. A single table (and single domain object) tracks the full journey — no need for separate `PendingMedia`, `ReadyMedia` tables. The tradeoff is that many fields are nullable. The state machine (below) defines which fields are populated at each state.

### Why `frozen=True`?

Immutability. Once a `Media` object is returned from the repository, nothing can mutate it in-place. Any "change" (e.g. transitioning to PROCESSING) creates a new `Media` instance using `dataclasses.replace()`. This prevents silent state drift as the object moves between service, router, and serialization layers.

---

## `MediaStatus` — The Status Constants

```python
class MediaStatus:
    PENDING    = "pending"
    PROCESSING = "processing"
    READY      = "ready"
    FAILED     = "failed"
    DELETING   = "deleting"

    ALL = frozenset({PENDING, PROCESSING, READY, FAILED, DELETING})
```

Using a class of string constants (like `UserStatus` for users) rather than a Python `Enum` keeps values as plain strings that serialize naturally to JSON and are stored as `VARCHAR(20)` in PostgreSQL. No ORM enum mapping needed.

---

## The State Machine

```
                        create_upload()
                              │
                              ▼
                         ┌─────────┐
                         │ PENDING │◄──────────────────────────────┐
                         └────┬────┘                               │
                              │ complete_upload()                  │ complete_upload()
                              │                                    │ (retry after FAILED)
              ┌───────────────┼──────────────────┐                │
              │               │                  │                │
              ▼               ▼                  ▼                │
     [upload URL expired] [object missing,  [size/content-type   │
              │            URL still valid]  mismatch]            │
              │               │                  │                │
              ▼               ▼                  ▼                │
         ┌────────┐      409 Conflict        ┌────────┐           │
         │ FAILED │◄────────────────────────►│ FAILED │───────────┘
         └────┬───┘   (cleanup_requested_at  └────┬───┘
              │        set on expiry)             │
              │                                   │
              │   object found, size+type OK       │
              └────────────────────┬──────────────┘
                                   │
                                   ▼
                            ┌────────────┐
                            │ PROCESSING │
                            └─────┬──────┘
                                  │
              ┌───────────────────┴───────────────┐
              │                                   │
              ▼                                   ▼
     [ImageMagick fails]               [variants stored OK]
              │                                   │
              ▼                                   ▼
         ┌────────┐                          ┌───────┐
         │ FAILED │                          │ READY │──── attached to post (RESTRICT FK)
         └────────┘                          └───┬───┘
                                                │
                                      discard() (if unattached)
                                                │
                                                ▼
                                          ┌──────────┐
                                          │ DELETING │
                                          └────┬─────┘
                                               │
                                    cleanup job: objects deleted
                                               │
                                               ▼
                                      [row hard-deleted]
```

### State Transition Rules

| From | To | Trigger | Condition |
| :--- | :--- | :--- | :--- |
| — | `PENDING` | `create_upload()` | Always |
| `PENDING` | `PROCESSING` | `complete_upload()` | Object found in storage, size + content-type match |
| `PENDING` | `FAILED` | `complete_upload()` | Upload URL has expired and object is missing |
| `PENDING` | `FAILED` | `complete_upload()` | Object found but size or content-type mismatch |
| `PROCESSING` | `READY` | `complete_upload()` | ImageMagick succeeds, both variants stored |
| `PROCESSING` | `FAILED` | `complete_upload()` | ImageMagick rejects the image |
| `FAILED` | `PROCESSING` | `complete_upload()` retry | Same flow as PENDING → PROCESSING |
| `READY` | `DELETING` | cleanup job | Media unattached and discard requested or grace period expired |
| `PENDING/FAILED` | `DELETING` | cleanup job | Abandoned for >24 hours |
| `DELETING` | *(deleted)* | cleanup job | All storage objects deleted successfully |

### What `READY` → `DELETING` requires

A `READY` media row is protected by a `UNIQUE` FK constraint on `post_media`. You **cannot** mark it for deletion while it is attached to a post. The service enforces this:

```python
attached = await self._repository.get_attached_ids([media_id])
if attached:
    raise MediaConflictError("attached media cannot be discarded")
```

And even if the application check is bypassed, the DB `ON DELETE RESTRICT` FK prevents the `post_media` row from orphaning.

---

## Field Population by State

| Field | PENDING | PROCESSING | READY | FAILED | DELETING |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id`, `owner_id` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `object_key` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `content_type` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `expected_size_bytes` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `upload_expires_at` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `size_bytes` | `None` | `None` | ✅ | `None` | ✅ or `None` |
| `width`, `height` | `None` | `None` | ✅ | `None` | ✅ or `None` |
| `display_object_key` | `None` | `None` | ✅ | `None` | ✅ or `None` |
| `thumbnail_object_key` | `None` | `None` | ✅ | `None` | ✅ or `None` |
| `failure_reason` | `None` | `None` | `None` | ✅ | `None` |
| `cleanup_requested_at` | `None` | `None` | `None`/✅ | `None`/✅ | ✅ |

---

## Questions to Revisit

- Should `status` become a Python `Enum` to get exhaustive match checking at the type level?
- Should `width` and `height` refer to the **original** or the **display** image dimensions? (Currently: original.)
- When a `FAILED` media is retried via `complete_upload()`, should a new `Media` record be created instead of reusing the same one?
