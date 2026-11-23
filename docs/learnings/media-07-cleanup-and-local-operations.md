# PR #13 — Chunk 7: Retryable Cleanup and Local Operations

> This final chunk covers cleanup across PostgreSQL and object storage, plus the local setup and test path.

## Why cleanup is a separate command

Object storage and PostgreSQL cannot commit atomically. Cleanup therefore runs as a retryable one-shot job (`make cleanup-media`) instead of deleting objects during a user-facing request.

The job can select unattached assets that are:

- Explicitly discarded.
- Abandoned in `PENDING`, `FAILED`, or `READY` beyond the configured grace period.
- Attached to posts soft-deleted beyond that grace period; those links are detached first.

Before removing an uploaded object, cleanup waits until its upload URL has expired plus a five-minute safety window. This prevents a still-valid presigned PUT from recreating an object after cleanup has already deleted it.

## Claim, delete, finalize

For each batch, the job:

1. Selects eligible unattached media rows and marks them `DELETING`.
2. Uses `FOR UPDATE SKIP LOCKED` so concurrent cleanup runs claim separate rows.
3. Commits the claim before contacting MinIO/S3.
4. Deletes the original and processed object keys.
5. Deletes the database row only after storage deletion succeeds and the row is still unattached.

If a storage delete fails, the row remains `DELETING`; a later run retries its object keys. Object deletes are treated as idempotent. The row is not removed from PostgreSQL on a partial failure, which keeps the work discoverable.

The job accepts a bounded batch size (100 by default). Run it periodically in the environment where the application database and storage are reachable. It is not automatically scheduled by the API process.

## Local development and configuration

Docker Compose starts MinIO with a private bucket created by the application on first use. The API container uses `http://minio:9000` internally, while browser-facing presigned URLs use the host endpoint (by default `http://127.0.0.1:9000`). Browser origins are configured for local Vite development.

Media settings are environment-configurable, including storage endpoints and credentials, bucket, upload/download URL TTLs, maximum upload bytes, and cleanup grace hours. Keep credentials in the local environment file; do not commit them. The backend Docker image contains ImageMagick; local host `make dev` requires ImageMagick to be installed.

Useful root commands:

```bash
make dev
make migrate
make cleanup-media
```

## What the tests prove

- Unit tests use fake repository, storage, and processor implementations to exercise the lifecycle without MinIO.
- Processing tests cover focused image processor behavior.
- The MinIO-backed API integration test is opt-in with `RUN_MEDIA_INTEGRATION_TESTS=1` and needs PostgreSQL, MinIO, and ImageMagick. It covers upload ticket creation, direct PUT, completion, post attachment, signed WebP delivery, and feed hydration.

The end-to-end test covers the happy path. PR #14 added dedicated coverage for invalid content, expired tickets without an uploaded object, transient object-read failures, and partial variant writes. Cleanup deletion-failure/retry still needs dedicated MinIO-backed integration coverage; see the follow-ups in the [media lifecycle decision](../adr/0004-image-media-lifecycle.md).
