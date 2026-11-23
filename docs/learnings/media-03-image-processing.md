# PR #13 — Chunk 3: Image Validation and Processing

> Read this after [Chunk 1: the media model](./media-01-domain-and-state-machine.md) and [Chunk 2: storage](./media-02-storage-layer.md).

This chunk follows an uploaded object from storage into validated, browser-ready image variants. The key principle is that the upload request's `content_type` and `size_bytes` are claims, not proof.

## Validation happens in layers

When the client calls `POST /api/v1/media/{media_id}/complete`, the service checks:

1. **Object metadata:** `HEAD` confirms the object exists, its actual size matches the declared size, it is within the configured maximum, and its stored content type does not contradict the declaration.
2. **File signature:** the processor recognizes JPEG, PNG, and WebP magic bytes and compares the detected type with the declaration.
3. **Decoded image:** ImageMagick reads the image and confirms the decoded format, dimensions, and frame count. Only a single frame is accepted.

The decoded image is limited to 8,000 pixels on either side and 40 million total pixels. Invalid, animated, oversized, or undecodable images fail processing and are recorded as `FAILED`; the API does not treat the client's filename or content type as authoritative.

## Why ImageMagick runs in a subprocess

`ImageMagickProcessor` invokes `identify` and `convert` using subprocesses, and runs its synchronous work in a thread so it does not block the async event loop. ImageMagick is configured with memory, map, disk, time, and thread limits. The subprocess also has a timeout.

This keeps image decoding outside the API process and bounds resource consumption. ImageMagick is a system dependency: the backend Docker image installs it, while local host development needs it installed separately.

## The two output variants

After validation, the processor creates:

| Variant | Output |
|---|---|
| Display | WebP, fit within 1600 × 1600, quality 85 |
| Thumbnail | WebP, center-cropped to 320 × 320, quality 80 |

Both variants are auto-oriented and stripped of metadata before being written to private storage. Stripping metadata removes embedded details such as GPS coordinates and camera information. The original remains in storage for the lifecycle's cleanup; post/feed delivery uses the display variant.

## Data passed back to the service

The processor returns a `ProcessedImage` containing the detected content type, original width and height, and the two output byte strings. The service stores those bytes under server-generated keys, then persists the dimensions, keys, actual byte size, and `READY` status on the media record.

If decoding or conversion fails, the service records a bounded failure reason and leaves the asset unavailable for post attachment. Object-storage failures are a separate failure class: they are not silently converted into a successful processing result.

## Where to look

- `backend/app/modules/media/processing.py` — signature detection, decode checks, limits, and transformations.
- `backend/app/modules/media/service.py` — object metadata checks and orchestration of the processor and storage writes.
- `backend/tests/modules/media/test_processing.py` — focused processing behavior.

The integration tests cover the successful upload-to-feed path plus invalid content, transient object-read failure/retry, and partial variant-write/retry. Cleanup deletion-failure/retry remains follow-up work; see the [media lifecycle decision](../adr/0004-image-media-lifecycle.md).
