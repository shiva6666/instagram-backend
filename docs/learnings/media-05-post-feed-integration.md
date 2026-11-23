# PR #13 — Chunk 5: Posts, Feeds, and Private Image Delivery

> This chunk connects a processed media asset to posts while preserving the existing URL-based API.

## Post creation accepts one image input style

Post creation supports:

- `media_ids` for newly uploaded assets.
- The legacy `post_img_url` field for existing clients and URL-backed images.

The two forms are mutually exclusive. A post must contain between one and ten images. For `media_ids`, `PostService` locks the selected rows and checks that every asset exists, belongs to the post author, is `READY`, is not scheduled for cleanup, and has the fields required for delivery. It also checks that no asset is already attached.

Only after those checks does the repository create the post and its ordered `post_media` rows. The post and links are part of the same PostgreSQL transaction. A unique constraint on `post_media.media_id` is the final guard against concurrent attempts to attach one asset more than once.

## Legacy URLs remain compatible

For URL-based post creation, the post repository creates a `READY` media record with the URL and no object key, then stores its media ID in the association table. Existing responses keep their `post_img_url` shape. This compatibility path does not make newly uploaded objects public.

## Authorization comes before signing

Post and feed services first select posts the viewer is permitted to see, applying their existing visibility, follow, block, and deletion rules. The routers then pass the visible posts' image references to `MediaUrlResolver`.

The resolver batch-loads media records for the page and:

- Returns a legacy URL unchanged for URL-backed images.
- Requires storage-backed media to be `READY` with a display key.
- Generates a short-lived signed GET URL for the private display object.

The resolver does not decide which posts are visible. Keeping that order means the temporary URL is only minted after the existing access checks have passed. A signed URL is a bearer capability until it expires, so it should remain short-lived and must not be logged.

Feed hydration gathers images across the returned page and resolves them together instead of issuing a media lookup per image. The response retains the established image URL field, so clients can continue rendering posts without knowing whether the source was legacy or storage-backed.

## Where to look

- `backend/app/modules/posts/service.py` — media ownership/readiness/attachment rules.
- `backend/app/modules/posts/repository.py` — ordered post-media persistence and legacy URL compatibility.
- `backend/app/modules/feed/repository.py` — set-based feed query and batched image loading.
- `backend/app/modules/feed/router.py` — URL resolution after feed selection.
- `backend/app/modules/media/service.py` — `MediaUrlResolver`.
- `backend/tests/modules/posts/test_posts_service.py` — media attachment checks.
- `backend/tests/modules/media/test_media_api_integration.py` — upload, attach, signed delivery, and feed hydration.
