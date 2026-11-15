from __future__ import annotations

import asyncio
import hashlib
import hmac
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from app.core.config import settings
from app.modules.media.storage.interfaces import (
    ObjectNotFoundError,
    ObjectStorageError,
    StoredObject,
)


class S3CompatibleStorage:
    """Small path-style AWS Signature V4 adapter for MinIO/S3.

    The public endpoint is used only for browser-facing presigned URLs. API
    operations use the internal endpoint so the app container never tries to
    connect to its own localhost.
    """

    def __init__(
        self,
        *,
        endpoint_url: str,
        public_endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
    ) -> None:
        self._endpoint_url = endpoint_url.rstrip("/")
        self._public_endpoint_url = public_endpoint_url.rstrip("/")
        self._bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region

    @classmethod
    def from_settings(cls) -> S3CompatibleStorage:
        return cls(
            endpoint_url=settings.media_storage_endpoint_url,
            public_endpoint_url=settings.media_storage_public_endpoint_url,
            bucket=settings.media_storage_bucket,
            access_key=settings.media_storage_access_key,
            secret_key=settings.media_storage_secret_key,
            region=settings.media_storage_region,
        )

    @staticmethod
    def _signing_key(secret: str, date: str, region: str) -> bytes:
        date_key = hmac.new(
            ("AWS4" + secret).encode(), date.encode(), hashlib.sha256
        ).digest()
        region_key = hmac.new(date_key, region.encode(), hashlib.sha256).digest()
        service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
        return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()

    def _presign(
        self,
        method: str,
        object_key: str | None,
        *,
        expires_in: int,
        public: bool,
    ) -> str:
        if not 1 <= expires_in <= 604800:
            raise ValueError("presigned URL expiry must be between 1 and 604800 seconds")
        endpoint = self._public_endpoint_url if public else self._endpoint_url
        parsed = urlsplit(endpoint)
        host = parsed.netloc
        raw_path = f"/{self._bucket}"
        if object_key is not None:
            raw_path += f"/{object_key}"
        canonical_uri = quote(raw_path, safe="/-_.~")
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        scope = f"{date_stamp}/{self._region}/s3/aws4_request"
        query = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self._access_key}/{scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires_in),
            "X-Amz-SignedHeaders": "host",
        }
        canonical_query = "&".join(
            f"{quote(key, safe='-_.~')}={quote(value, safe='-_.~')}"
            for key, value in sorted(query.items())
        )
        canonical_request = (
            f"{method}\n{canonical_uri}\n{canonical_query}\n"
            f"host:{host}\n\nhost\nUNSIGNED-PAYLOAD"
        )
        string_to_sign = (
            "AWS4-HMAC-SHA256\n"
            f"{amz_date}\n{scope}\n"
            f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        )
        signature = hmac.new(
            self._signing_key(self._secret_key, date_stamp, self._region),
            string_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()
        return (
            f"{parsed.scheme}://{host}{canonical_uri}?"
            f"{canonical_query}&X-Amz-Signature={signature}"
        )

    def presign_put_url(self, object_key: str, *, expires_in: int) -> str:
        return self._presign(
            "PUT", object_key, expires_in=expires_in, public=True
        )

    def presign_get_url(self, object_key: str, *, expires_in: int) -> str:
        return self._presign(
            "GET", object_key, expires_in=expires_in, public=True
        )

    def _request_sync(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        missing_is_ok: bool = False,
        max_bytes: int | None = None,
    ) -> tuple[bytes, object] | None:
        request = Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                if max_bytes is not None:
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > max_bytes:
                        raise ObjectStorageError(
                            "object exceeds the configured size limit"
                        )
                    body = response.read(max_bytes + 1)
                    if len(body) > max_bytes:
                        raise ObjectStorageError(
                            "object exceeds the configured size limit"
                        )
                else:
                    body = response.read()
                return body, response.headers
        except HTTPError as error:
            if error.code == 404 and missing_is_ok:
                return None
            raise ObjectStorageError(
                f"object storage returned HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise ObjectStorageError("object storage request failed") from error

    async def ensure_bucket(self) -> None:
        head_url = self._presign(
            "HEAD", None, expires_in=60, public=False
        )
        result = await asyncio.to_thread(
            self._request_sync, "HEAD", head_url, missing_is_ok=True
        )
        if result is not None:
            return
        create_url = self._presign(
            "PUT", None, expires_in=60, public=False
        )
        await asyncio.to_thread(self._request_sync, "PUT", create_url)

    async def head_object(self, object_key: str) -> StoredObject:
        url = self._presign("HEAD", object_key, expires_in=60, public=False)
        result = await asyncio.to_thread(
            self._request_sync, "HEAD", url, missing_is_ok=True
        )
        if result is None:
            raise ObjectNotFoundError("uploaded object was not found")
        _body, headers = result
        return StoredObject(
            size_bytes=int(headers.get("Content-Length", "0")),
            content_type=headers.get("Content-Type"),
        )

    async def get_object(self, object_key: str, *, max_bytes: int) -> bytes:
        url = self._presign("GET", object_key, expires_in=60, public=False)
        result = await asyncio.to_thread(
            self._request_sync, "GET", url, max_bytes=max_bytes
        )
        if result is None:
            raise ObjectNotFoundError("object was not found")
        body, _headers = result
        return body

    async def put_object(
        self, object_key: str, data: bytes, *, content_type: str
    ) -> None:
        url = self._presign("PUT", object_key, expires_in=60, public=False)
        await asyncio.to_thread(
            self._request_sync,
            "PUT",
            url,
            data=data,
            headers={"Content-Type": content_type},
        )

    async def delete_object(self, object_key: str) -> None:
        url = self._presign("DELETE", object_key, expires_in=60, public=False)
        await asyncio.to_thread(
            self._request_sync, "DELETE", url, missing_is_ok=True
        )
