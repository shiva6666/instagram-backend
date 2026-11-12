from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, *, private: bool = False) -> tuple[str, str]:
    suffix = secrets.token_hex(5)
    username = f"user_{suffix}"
    email = f"{username}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "a-strong-test-password",
            "is_private": private,
        },
    )
    assert response.status_code == 201, response.text
    return username, response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_private_follow_request_acceptance_and_unfollow_use_postgresql() -> None:
    with TestClient(app) as client:
        private_user, private_token = _register(client, private=True)
        follower, follower_token = _register(client)

        requested = client.post(
            f"/api/v1/follows/{private_user}",
            headers=_auth(follower_token),
        )
        assert requested.status_code == 200, requested.text
        assert requested.json()["status"] == "pending"

        pending = client.get(
            f"/api/v1/follows/{private_user}/relationship",
            headers=_auth(follower_token),
        )
        assert pending.status_code == 200
        assert pending.json()["request_pending"] is True
        assert pending.json()["is_following"] is False

        hidden_list = client.get(
            f"/api/v1/follows/{private_user}/followers",
            headers=_auth(follower_token),
        )
        assert hidden_list.status_code == 404

        accepted = client.post(
            f"/api/v1/follows/requests/{follower}/accept",
            headers=_auth(private_token),
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "accepted"

        relationship = client.get(
            f"/api/v1/follows/{private_user}/relationship",
            headers=_auth(follower_token),
        )
        assert relationship.status_code == 200
        assert relationship.json()["is_following"] is True

        followers = client.get(
            f"/api/v1/follows/{private_user}/followers",
            headers=_auth(follower_token),
        )
        assert followers.status_code == 200, followers.text
        assert [item["username"] for item in followers.json()["users"]] == [follower]

        counts = client.get(
            f"/api/v1/follows/{private_user}/counts",
            headers=_auth(follower_token),
        )
        assert counts.status_code == 200
        assert counts.json()["followers"] == 1

        removed = client.delete(
            f"/api/v1/follows/{private_user}",
            headers=_auth(follower_token),
        )
        assert removed.status_code == 204

        after_unfollow = client.get(
            f"/api/v1/follows/{private_user}/relationship",
            headers=_auth(follower_token),
        )
        assert after_unfollow.status_code == 200
        assert after_unfollow.json()["status"] is None


def test_public_follow_is_idempotent_and_self_follow_is_rejected() -> None:
    with TestClient(app) as client:
        target, _ = _register(client)
        follower, follower_token = _register(client)

        first = client.post(
            f"/api/v1/follows/{target}", headers=_auth(follower_token)
        )
        second = client.post(
            f"/api/v1/follows/{target}", headers=_auth(follower_token)
        )
        self_follow = client.post(
            f"/api/v1/follows/{follower}", headers=_auth(follower_token)
        )

        assert first.status_code == 200, first.text
        assert first.json()["status"] == "accepted"
        assert second.status_code == 200, second.text
        assert second.json()["created_at"] == first.json()["created_at"]
        assert self_follow.status_code == 400
