# PR #13 — Chunk 2: Storage Layer (MinIO / S3)

> This chunk explains why object storage exists, how the `ObjectStorage` protocol works, and how the hand-rolled S3 adapter signs requests without boto3.

---

## Why Object Storage At All?

Before PR #13, the backend accepted a plain URL string from the client and stored it. Problems:

- The backend never saw the image bytes — it couldn't validate, resize, or secure them.
- Images were hosted on third-party servers the backend didn't control.
- There was no way to enforce access control — anyone with the URL could view any image.
- Private posts had publicly accessible images if someone guessed the URL.

Object storage (MinIO in development, S3 in production) solves all of this:

| Problem | Solution |
| :--- | :--- |
| Backend doesn't see the bytes | Backend controls all object keys and verifies via HEAD/GET after upload |
| Third-party hosting | Private MinIO bucket — the backend owns the storage |
| No access control | All GET URLs are **presigned** and expire after 15 minutes |
| Private post leak | Signed GET URL is only generated **after** feed/post visibility is checked |

---

## Why Presigned URLs? (Browser → MinIO Direct Upload)

A naive design would be:

```
Browser → POST /api/v1/media/upload (multipart/form-data)
API → receives image bytes in memory → validates → stores to MinIO
```

**Problems with this:**
- 10MB images flow through the API process, consuming memory and CPU for every concurrent upload.
- File transfer is serialized through a single app bottleneck.
- Timeouts are more likely on slow connections.

**The PR's design:**

```
Browser → POST /api/v1/media/upload-url         (tiny JSON request)
API     → returns presigned PUT URL             (the URL is the capability)
Browser → PUT <presigned URL> (direct to MinIO) (bypasses the API entirely)
Browser → POST /api/v1/media/{id}/complete      (signals readiness)
```

The API never touches the image bytes during the upload phase. MinIO absorbs the bandwidth directly.

---

## The `ObjectStorage` Protocol

```python
class ObjectStorage(Protocol):
    def presign_put_url(self, object_key: str, *, expires_in: int) -> str: ...
    def presign_get_url(self, object_key: str, *, expires_in: int) -> str: ...
    async def ensure_bucket(self) -> None: ...
    async def head_object(self, object_key: str) -> StoredObject: ...
    async def get_object(self, object_key: str, *, max_bytes: int) -> bytes: ...
    async def put_object(self, object_key: str, data: bytes, *, content_type: str) -> None: ...
    async def delete_object(self, object_key: str) -> None: ...
```

**Why Protocol (not ABC)?**
`MediaService` only imports `ObjectStorage`, never `S3CompatibleStorage`. Tests inject a `FakeObjectStorage` that records calls without touching any network. The concrete implementation can be replaced (e.g. Azure Blob Storage) without changing the service.

**`presign_put_url` and `presign_get_url` are synchronous** because URL signing is a pure in-memory cryptographic operation (HMAC-SHA256). No I/O, no blocking — no need for `async`.

**All other methods are async** because they make network calls to object storage.

---

## Why Not `boto3` or `aioboto3`?

The PR implements AWS Signature V4 from scratch. This was deliberate:

| Concern | boto3 | Hand-rolled |
| :--- | :--- | :--- |
| Dependency size | ~12MB (botocore) | Zero extra deps |
| Async support | Needs aioboto3 wrapper | Native `asyncio.to_thread()` |
| Dual endpoint (internal/public) | Requires custom endpoint config | Built-in by design |
| Import time | Slow (heavy botocore init) | Instant |
| Works with MinIO | Yes (but extra config) | Yes (path-style by default) |

For a small set of S3 operations (HEAD, GET, PUT, DELETE, presign), the full boto3 stack is unnecessary overhead.

---

## The Dual Endpoint Problem

This is the most subtle part of the storage layer. In Docker Compose:

```yaml
services:
  api:
    environment:
      MEDIA_STORAGE_ENDPOINT_URL: "http://minio:9000"         # internal
      MEDIA_STORAGE_PUBLIC_ENDPOINT_URL: "http://localhost:9000"  # for browsers
  minio:
    ports:
      - "9000:9000"
```

**Why two URLs?**

| Caller | Needs to reach | URL |
| :--- | :--- | :--- |
| API container | MinIO container | `http://minio:9000` (Docker internal DNS) |
| Browser | MinIO exposed port | `http://localhost:9000` (host-mapped port) |

If the API signed presigned URLs using `http://minio:9000`, the browser would try to fetch `http://minio:9000/...` — which doesn't resolve from outside Docker. The browser needs `http://localhost:9000`.

**Solution in `S3CompatibleStorage._presign()`:**

```python
def _presign(self, method, object_key, *, expires_in, public: bool) -> str:
    endpoint = self._public_endpoint_url if public else self._endpoint_url
    ...
```

- `presign_put_url()` and `presign_get_url()` → `public=True` → uses `public_endpoint_url` → browser-facing
- Internal ops (`head_object`, `get_object`, `put_object`, `delete_object`) → `public=False` → uses `endpoint_url` → container-to-container

---

## AWS Signature V4 — How the Signing Works

The presigned URL is a standard HTTP request that is pre-authorized using an HMAC signature. Here's the flow:

```python
# 1. Build a "scope" that ties the signature to a date/region/service
scope = f"{date_stamp}/{region}/s3/aws4_request"

# 2. Build query parameters that describe the authorization
query = {
    "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
    "X-Amz-Credential": f"{access_key}/{scope}",
    "X-Amz-Date": amz_date,
    "X-Amz-Expires": str(expires_in),
    "X-Amz-SignedHeaders": "host",
}

# 3. Build a canonical representation of the request
canonical_request = f"{method}\n{uri}\n{sorted_query}\nhost:{host}\n\nhost\nUNSIGNED-PAYLOAD"

# 4. Build a "string to sign"
string_to_sign = f"AWS4-HMAC-SHA256\n{date}\n{scope}\n{sha256(canonical_request)}"

# 5. Derive a signing key (HMAC chain: date → region → service → "aws4_request")
signing_key = HMAC(HMAC(HMAC(HMAC("AWS4"+secret, date), region), "s3"), "aws4_request")

# 6. Compute the signature
signature = HMAC(signing_key, string_to_sign).hexdigest()

# 7. Append signature to URL
url = f"{endpoint}/{bucket}/{object_key}?{query}&X-Amz-Signature={signature}"
```

**What makes the URL secure?**
- The HMAC signature is computed using the secret key — only the backend can produce it.
- The URL encodes the method (PUT or GET), the exact object key, and an expiry time.
- MinIO/S3 validates the signature and the expiry before honoring the request.
- A presigned PUT URL for `original/.../source` cannot be used to GET or to write to any other path.

**`UNSIGNED-PAYLOAD`** means the signature doesn't cover the request body hash. This is standard practice for presigned PUTs where the browser uploads arbitrary bytes — requiring a body hash would force the browser to compute SHA256 of the full file before uploading.

---

## Object Key Structure

```
original/{owner_id}/{media_id}/source          ← raw upload from browser
processed/{owner_id}/{media_id}/display.webp   ← 1600px display image
processed/{owner_id}/{media_id}/thumbnail.webp ← 320×320 center-crop thumbnail
```

**Why include `owner_id` in the path?**

Even with a private bucket, defense-in-depth: if a presigned URL is ever accidentally generated for the wrong media_id, the `owner_id` prefix prevents one user's object key from colliding with another's. Guessing `media_id` without knowing `owner_id` is effectively impossible (both are UUIDv7).

---

## `ensure_bucket()` — Idempotent Bucket Creation

```python
async def ensure_bucket(self) -> None:
    head_url = self._presign("HEAD", None, expires_in=60, public=False)
    result = await asyncio.to_thread(self._request_sync, "HEAD", head_url, missing_is_ok=True)
    if result is not None:
        return   # bucket already exists
    create_url = self._presign("PUT", None, expires_in=60, public=False)
    await asyncio.to_thread(self._request_sync, "PUT", create_url)
```

Called at the start of `create_upload()`. In development, the bucket may not exist yet. Rather than requiring a manual setup step, the app creates it on first use. Safe to call repeatedly — HEAD returns 200 if it exists, 404 if not.

---

## `asyncio.to_thread()` — Why Sync HTTP?

The adapter uses Python's `urllib` (synchronous) for all object operations, offloaded via `asyncio.to_thread()`. Why not `aiohttp` or `httpx`?

- **Fewer dependencies** — `urllib` is in the standard library.
- **Simplicity** — sync code is easier to reason about for one-off operations.
- **`asyncio.to_thread()`** runs the sync function in a thread pool, so the event loop is never blocked.

The 15-second timeout on `urlopen` ensures a stalled MinIO never hangs a request indefinitely.

---

## Questions to Revisit

- In production, `public_endpoint_url` should be a CDN (e.g. CloudFront). How does that affect Signature V4 signing?
- Should `ensure_bucket()` only run at app startup (via lifespan hook) rather than on every upload request?
- Should the storage adapter be replaced with a thin `aioboto3` wrapper when the project scales?
