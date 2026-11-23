# PR #13 — Chunk 6: Schema Migration and Legacy Data

> This chunk explains how PR #13 introduced media records without dropping existing post images.

## Two tables, two responsibilities

Migration `005_media_assets` adds:

- **`media`** — owner, lifecycle status, legacy URL or storage keys, declared/actual size, dimensions, upload expiry, cleanup request, and failure reason.
- **`post_media`** — the ordered relationship between a post and one media asset.

The media table has a status check and positive-size/dimension constraints, plus indexes used by owner queries and cleanup. The association has a foreign key to media with `ON DELETE RESTRICT` and a unique constraint on `media_id`: a media asset can be attached to at most one post.

## Converting existing `post_images`

The upgrade preserves the old rows rather than requiring users to recreate posts:

1. Create the new `media` table.
2. Add a media ID to each existing `post_images` row.
3. Insert one `READY` media record per old image, copying its URL and deriving its owner from the associated post.
4. Rename `post_images` to `post_media`, make the media ID required, and add the foreign key and uniqueness constraint.

These migrated rows have a URL and no object key. They remain deliverable through the legacy URL path. New uploads instead have server-generated object keys and receive signed URLs.

## Why the downgrade can refuse

The old schema can represent a URL, but it cannot represent a private object stored in MinIO/S3. Downgrade therefore checks before changing tables and raises an error if storage-backed media exists or if an attached media row has no legacy URL. Refusing is safer than silently converting a valid post into a broken image link.

The guard is conservative: operators should resolve or intentionally migrate the affected assets before attempting a downgrade.

## Where to look

- `backend/migrations/versions/005_media_assets.py` — upgrade, data backfill, constraints, and downgrade guard.
- `backend/app/modules/media/repository.py` — ORM mapping for the `media` table.
- `backend/app/modules/posts/repository.py` — ORM mapping and compatibility persistence for `post_media`.
- `docs/adr/0002-image-media-lifecycle.md` — the decisions behind this schema.

Apply migrations through the existing root command: `make migrate`.
