# PR #13 — Chunk 4: Upload API and Service Flow

> This chunk explains the authenticated HTTP endpoints and the application service that coordinates them.

## The API surface

Every media endpoint requires an authenticated user. The router translates application errors into HTTP responses; the service enforces ownership and lifecycle rules.

| Endpoint | Purpose | Important response behavior |
|---|---|---|
| `POST /api/v1/media/upload-url` | Validate declared type/size, create a pending media record, and return a presigned upload ticket | `201`; invalid type or size returns `422` |
| `POST /api/v1/media/{media_id}/complete` | Verify the stored object and process it | Returns current status; missing media is `404`, wrong owner is `403`, incomplete upload or invalid state is `409` |
| `GET /api/v1/media/{media_id}` | Read the caller's processing status | Owner-scoped; `404` or `403` for missing/other-user assets |
| `DELETE /api/v1/media/{media_id}` | Schedule an unattached asset for cleanup | `202`; attached assets return `409` |

The upload ticket includes `media_id`, `upload_url`, the required `content_type`, and `expires_at`. The client must use that content type on its direct `PUT` to object storage.

## Ticket creation

`MediaService.create_upload()`:

1. Allows JPEG, PNG, and WebP and checks that the declared size is positive and within the configured maximum.
2. Ensures the private bucket exists.
3. Generates the media ID and an object key scoped to the owner and media ID; client filenames are not used.
4. Creates a `PENDING` media record with the declared size and upload expiry.
5. Signs a short-lived PUT URL and returns the ticket.

The API handles only the small ticket request. The browser sends the image bytes directly to MinIO/S3.

## Completion

`complete_upload()` locks the media row before changing lifecycle state. It checks ownership, disallows completion when cleanup is scheduled, and returns a `READY` record unchanged on a repeated completion request.

For a pending or failed record, the service checks object metadata. If the object is missing while the URL is still valid, it reports that the client should upload first. If the URL expired with no object, the record is failed and scheduled for cleanup. A size or content-type mismatch also fails the record.

With valid metadata, the service saves `PROCESSING`, downloads a bounded number of bytes, asks the image processor to validate and create variants, writes the display and thumbnail objects, then saves `READY`. Invalid images are recorded as `FAILED`. The status endpoint lets clients inspect the result.

## Important reliability boundary

PostgreSQL and object storage do not share a transaction. Completion currently performs storage I/O and image processing inline while the request is in progress. A storage error can therefore leave partial external state, and long processing affects request latency. The lifecycle and cleanup paths provide retry/repair support, but this is not yet a durable worker or an atomic cross-system operation.

## Discard is scheduled, not immediate

Discard verifies that the asset belongs to the caller and is not attached to a post. It sets `cleanup_requested_at` and returns `202`; it does not synchronously delete the object. The cleanup command later coordinates object deletion and row removal. This avoids returning success after only one side of the storage/database cleanup has completed.

## Where to look

- `backend/app/modules/media/router.py` — HTTP endpoints and error mapping.
- `backend/app/modules/media/schemas.py` — request and response shapes.
- `backend/app/modules/media/service.py` — validation and lifecycle orchestration.
- `backend/app/modules/media/dependencies.py` — construction and injection of dependencies.
- `backend/tests/modules/media/test_media_service.py` — service behavior with fake storage and repository implementations.
