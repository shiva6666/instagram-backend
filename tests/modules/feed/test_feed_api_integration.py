from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app.main import app


def _register(
    client: TestClient, *, private: bool = False
) -> tuple[str, str]:
    username = f"feed_{secrets.token_hex(5)}"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "a-strong-test-password",
            "is_private": private,
        },
    )
    assert response.status_code == 201, response.text
    return username, response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_post(
    client: TestClient,
    token: str,
    caption: str,
    *,
    private: bool = False,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/posts",
        headers=_auth(token),
        json={
            "caption": caption,
            "post_img_url": [{"url": f"https://cdn.example/{caption}.jpg"}],
            "is_private": private,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_home_feed_filters_visibility_and_uses_cursor_pagination() -> None:
    with TestClient(app) as client:
        viewer, viewer_token = _register(client)
        followed, followed_token = _register(client)
        private_author, private_author_token = _register(client, private=True)
        stranger, stranger_token = _register(client)

        followed_response = client.post(
            f"/api/v1/follows/{followed}",
            headers=_auth(viewer_token),
        )
        assert followed_response.status_code == 200, followed_response.text

        private_request = client.post(
            f"/api/v1/follows/{private_author}",
            headers=_auth(viewer_token),
        )
        assert private_request.status_code == 200, private_request.text
        assert private_request.json()["status"] == "pending"

        accepted = client.post(
            f"/api/v1/follows/requests/{viewer}/accept",
            headers=_auth(private_author_token),
        )
        assert accepted.status_code == 200, accepted.text

        _create_post(client, followed_token, "followed-public")
        _create_post(client, followed_token, "followed-private", private=True)
        _create_post(client, private_author_token, "private-account-post")
        _create_post(client, stranger_token, "stranger-post")
        _create_post(client, viewer_token, "viewer-own-post")

        first = client.get("/api/v1/feed?limit=2", headers=_auth(viewer_token))
        assert first.status_code == 200, first.text
        first_payload = first.json()
        assert [post["caption"] for post in first_payload["posts"]] == [
            "viewer-own-post",
            "private-account-post",
        ]
        assert first_payload["next_cursor"] is not None

        second = client.get(
            f"/api/v1/feed?limit=2&cursor={first_payload['next_cursor']}",
            headers=_auth(viewer_token),
        )
        assert second.status_code == 200, second.text
        second_payload = second.json()
        assert [post["caption"] for post in second_payload["posts"]] == [
            "followed-public"
        ]
        assert second_payload["next_cursor"] is None

        returned_posts = first_payload["posts"] + second_payload["posts"]
        returned_ids = {post["id"] for post in returned_posts}
        assert len(returned_ids) == 3
        assert stranger not in {post["username"] for post in returned_posts}
        assert viewer in {post["username"] for post in returned_posts}
        assert all(post["caption"] != "followed-private" for post in returned_posts)


def test_home_feed_rejects_invalid_cursor() -> None:
    with TestClient(app) as client:
        _viewer, viewer_token = _register(client)
        response = client.get(
            "/api/v1/feed?cursor=not-a-valid-cursor",
            headers=_auth(viewer_token),
        )
        assert response.status_code == 422
