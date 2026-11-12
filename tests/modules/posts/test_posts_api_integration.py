from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient) -> tuple[str, str]:
    suffix = secrets.token_hex(5)
    username = f"posts_{suffix}"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "a-strong-test-password",
        },
    )
    assert response.status_code == 201, response.text
    return username, response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_author_post_visibility_is_filtered_before_cursor_pagination() -> None:
    with TestClient(app) as client:
        author, author_token = _register(client)
        viewer, viewer_token = _register(client)

        for caption, is_private in (
            ("public-old", False),
            ("public-new", False),
            ("private-newest", True),
        ):
            created = client.post(
                "/api/v1/posts",
                headers=_auth(author_token),
                json={
                    "caption": caption,
                    "post_img_url": [{"url": "https://cdn.example/image.jpg"}],
                    "is_private": is_private,
                },
            )
            assert created.status_code == 201, created.text

        first = client.get(
            f"/api/v1/posts/users/{author}?limit=1",
            headers=_auth(viewer_token),
        )
        assert first.status_code == 200, first.text
        first_payload = first.json()
        assert len(first_payload["posts"]) == 1
        assert first_payload["posts"][0]["caption"].startswith("public")
        assert first_payload["next_cursor"] is not None

        second = client.get(
            f"/api/v1/posts/users/{author}?limit=1&cursor={first_payload['next_cursor']}",
            headers=_auth(viewer_token),
        )
        assert second.status_code == 200, second.text
        second_payload = second.json()
        assert len(second_payload["posts"]) == 1
        assert second_payload["posts"][0]["caption"].startswith("public")
        assert second_payload["next_cursor"] is None
        assert first_payload["posts"][0]["id"] != second_payload["posts"][0]["id"]

        own_posts = client.get(
            f"/api/v1/posts/users/{author}?limit=10",
            headers=_auth(author_token),
        )
        assert own_posts.status_code == 200, own_posts.text
        assert len(own_posts.json()["posts"]) == 3
