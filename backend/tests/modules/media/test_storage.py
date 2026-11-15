from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from app.modules.media.storage.s3 import S3CompatibleStorage


def test_presigned_upload_and_download_urls_use_configured_public_endpoint() -> None:
    storage = S3CompatibleStorage(
        endpoint_url="http://minio:9000",
        public_endpoint_url="http://127.0.0.1:9000",
        bucket="instagram-media",
        access_key="test-access",
        secret_key="test-secret",
    )

    upload = urlsplit(
        storage.presign_put_url("original/user/media/source", expires_in=300)
    )
    download = urlsplit(
        storage.presign_get_url("processed/user/media/display.webp", expires_in=600)
    )

    assert upload.scheme == "http"
    assert upload.netloc == "127.0.0.1:9000"
    assert upload.path == "/instagram-media/original/user/media/source"
    assert parse_qs(upload.query)["X-Amz-Expires"] == ["300"]
    assert parse_qs(upload.query)["X-Amz-SignedHeaders"] == ["host"]
    assert download.path.endswith("/processed/user/media/display.webp")
    assert parse_qs(download.query)["X-Amz-Expires"] == ["600"]
    assert "X-Amz-Signature" in parse_qs(upload.query)
