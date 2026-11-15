# Backend application

This directory contains the FastAPI modular monolith, Python dependencies,
Alembic migrations, backend tests, and development scripts.

From the repository root, use the root Makefile:

- `make dev` — start the API and Vite frontend with local PostgreSQL/Redis.
- `make test` — run backend tests.
- `make lint` — run Ruff.
- `make typecheck` — run mypy.
- `make migrate` — apply Alembic migrations.
- `make seed` — populate local demo data.

For direct backend commands, run them from this directory with `uv`.
The local environment file remains at the repository root; application
settings resolve it from the repository location regardless of the process
working directory.


## Media uploads

The media API uses MinIO locally and keeps uploaded objects private. The browser
uploads bytes directly to a short-lived presigned URL; the API verifies and
processes the object before it can be attached to a post.

1. Request an upload ticket:

   ```http
   POST /api/v1/media/upload-url
   Authorization: Bearer <access-token>
   Content-Type: application/json

   {"content_type": "image/jpeg", "size_bytes": 245812}
   ```

2. Upload the raw bytes with an HTTP `PUT` to the returned `upload_url`, using
   the exact `Content-Type` returned by the API.
3. Finalize processing:

   ```http
   POST /api/v1/media/<media-id>/complete
   Authorization: Bearer <access-token>
   ```

4. Create a post using the ready media IDs:

   ```json
   {
     "caption": "A day outside",
     "media_ids": ["<media-id>"]
   }
   ```

The old `post_img_url` post payload remains supported for compatibility.
Post and feed responses generate short-lived signed read URLs only after the
existing visibility checks have succeeded.

Supported input formats are JPEG, PNG, and WebP, up to 10 MiB per image.
ImageMagick validates/decodes the source and creates metadata-stripped WebP
display and thumbnail variants. Install ImageMagick on the host when using
`make dev`; the backend Docker image includes it.

Discarding an unattached asset with `DELETE /api/v1/media/<media-id>` schedules
it for cleanup. `make cleanup-media` removes explicitly discarded assets and
unattached assets older than the configured 24-hour grace period. Run this
command periodically in development/operations. Cleanup claims rows before
deleting objects and is safe to retry. Media attached to soft-deleted posts is
also detached and cleaned up after the same grace period.

The completion endpoint performs bounded image processing inline in this
first vertical slice. A durable background worker and asynchronous processing
queue remain a later reliability milestone; the media state model and retry
behavior are designed to support that evolution.
