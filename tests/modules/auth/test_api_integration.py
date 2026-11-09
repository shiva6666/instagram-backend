from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app.main import app


def test_authentication_journey_uses_postgresql() -> None:
    """Exercise the public auth flow against the PostgreSQL schema in CI."""
    suffix = secrets.token_hex(6)
    email = f"smoke-{suffix}@example.test"
    password = "a-strong-test-password"

    with TestClient(app) as client:
        register = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"smoke_{suffix}",
                "email": email,
                "password": password,
            },
        )
        assert register.status_code == 201, register.text
        initial_tokens = register.json()

        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200, login.text
        logged_in_tokens = login.json()

        current_user = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {logged_in_tokens['access_token']}"},
        )
        assert current_user.status_code == 200, current_user.text
        assert current_user.json()["email"] == email

        refresh = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": initial_tokens["refresh_token"]},
        )
        assert refresh.status_code == 200, refresh.text
        rotated_refresh_token = refresh.json()["refresh_token"]

        logout = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": rotated_refresh_token},
        )
        assert logout.status_code == 200, logout.text

        revoked_refresh = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": rotated_refresh_token},
        )
        assert revoked_refresh.status_code == 401, revoked_refresh.text
