from __future__ import annotations

import os
import secrets
import struct
import zlib
from urllib.request import Request, urlopen

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MEDIA_INTEGRATION_TESTS") != "1",
    reason="requires PostgreSQL, MinIO, and ImageMagick",
)


def _png_bytes() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    pixels = b"\x00" + b"\xff\x00\x00" * 2 + b"\x00" + b"\x00\xff\x00" * 2
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def _register(client: TestClient) -> str:
    suffix = secrets.token_hex(5)
    username = f"media_{suffix}"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "a-strong-test-password",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_upload_process_attach_and_read_media_end_to_end() -> None:
    image_bytes = _png_bytes()
    with TestClient(app) as client:
        token = _register(client)
        headers = {"Authorization": f"Bearer {token}"}

        ticket_response = client.post(
            "/api/v1/media/upload-url",
            headers=headers,
            json={"content_type": "image/png", "size_bytes": len(image_bytes)},
        )
        assert ticket_response.status_code == 201, ticket_response.text
        ticket = ticket_response.json()

        upload_request = Request(
            ticket["upload_url"],
            data=image_bytes,
            headers={"Content-Type": "image/png"},
            method="PUT",
        )
        with urlopen(upload_request, timeout=10) as upload_response:
            assert upload_response.status in {200, 201}

        completed = client.post(
            f"/api/v1/media/{ticket['media_id']}/complete",
            headers=headers,
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "ready"
        assert completed.json()["width"] == 2
        assert completed.json()["height"] == 2

        created = client.post(
            "/api/v1/posts",
            headers=headers,
            json={
                "caption": "uploaded through MinIO",
                "media_ids": [ticket["media_id"]],
            },
        )
        assert created.status_code == 201, created.text
        post = created.json()
        assert post["post_img_url"][0]["url"].startswith("http://")

        with urlopen(post["post_img_url"][0]["url"], timeout=10) as image_response:
            assert image_response.headers.get_content_type() == "image/webp"
            assert image_response.read().startswith(b"RIFF")

        feed = client.get("/api/v1/feed", headers=headers)
        assert feed.status_code == 200, feed.text
        assert any(item["id"] == post["id"] for item in feed.json()["posts"])

        discarded = client.delete(
            f"/api/v1/media/{ticket['media_id']}",
            headers=headers,
        )
        assert discarded.status_code == 409
