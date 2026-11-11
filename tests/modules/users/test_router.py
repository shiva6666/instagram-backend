"""Route-level tests for the users router.

Uses FastAPI's TestClient with dependency overrides.  No database required.

Covers:
  - GET /api/v1/users/me → 200 own profile (authenticated)
  - GET /api/v1/users/me → 401 without token
  - PATCH /api/v1/users/me → 200 successful update
  - PATCH /api/v1/users/me → 403 suspended account
  - PATCH /api/v1/users/me → 403 pending-deletion account
  - GET /api/v1/users/{username} → 200 public profile, safe fields only
  - GET /api/v1/users/{username} → 404 unknown username
  - GET /api/v1/users/{username} → 404 suspended account (not leaked)
  - GET /api/v1/users/{username} → 404 pending-deletion account (not leaked)
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User, UserStatus
from app.modules.users.repository import UserAlreadyExistsError
from app.modules.users.router import get_user_service
from app.modules.users.service import UserService

# ---------------------------------------------------------------------------
# Shared user fixtures
# ---------------------------------------------------------------------------

_FIXED_NOW = datetime(2026, 11, 10, 0, 0, 0, tzinfo=UTC)
_ALICE_ID: UUID = uuid4()

_ALICE = User(
    id=_ALICE_ID,
    username="alice",
    email="alice@example.com",
    bio="Hi there",
    avatar_key=None,
    is_private=False,
    status=UserStatus.ACTIVE,
    created_at=_FIXED_NOW,
    updated_at=_FIXED_NOW,
)

_SUSPENDED_USER = User(
    id=uuid4(),
    username="suspended_sam",
    email="sam@example.com",
    bio=None,
    avatar_key=None,
    is_private=False,
    status=UserStatus.SUSPENDED,
    created_at=_FIXED_NOW,
    updated_at=_FIXED_NOW,
)

_PENDING_USER = User(
    id=uuid4(),
    username="pending_pat",
    email="pat@example.com",
    bio=None,
    avatar_key=None,
    is_private=False,
    status=UserStatus.PENDING_DELETION,
    created_at=_FIXED_NOW,
    updated_at=_FIXED_NOW,
)


# ---------------------------------------------------------------------------
# In-memory fake repository and service factory
# ---------------------------------------------------------------------------


class FakeUserRepository:
    def __init__(self, store: dict[UUID, User]) -> None:
        self._store = store

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._store.get(user_id)

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._store.values() if u.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._store.values() if u.email == email), None)

    async def add(self, user: User) -> User:
        if any(
            u.username == user.username or u.email == user.email
            for u in self._store.values()
        ):
            raise UserAlreadyExistsError
        self._store[user.id] = user
        return user

    async def save(self, user: User) -> User:
        self._store[user.id] = user
        return user


def _make_fake_service(store: dict[UUID, User]) -> UserService:
    return UserService(FakeUserRepository(dict(store)))


# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------

_DEFAULT_STORE: dict[UUID, User] = {
    _ALICE.id: _ALICE,
    _SUSPENDED_USER.id: _SUSPENDED_USER,
    _PENDING_USER.id: _PENDING_USER,
}


def _client(
    current_user: User | None = _ALICE,
    store: dict[UUID, User] | None = None,
) -> TestClient:
    resolved_store = store if store is not None else _DEFAULT_STORE

    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user

    app.dependency_overrides[get_user_service] = lambda: _make_fake_service(
        resolved_store
    )

    return TestClient(app, raise_server_exceptions=True)


def _teardown() -> None:
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------


def test_get_own_profile_returns_full_fields() -> None:
    client = _client(current_user=_ALICE)
    try:
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "alice"
        assert body["email"] == "alice@example.com"  # private field included
        assert body["status"] == UserStatus.ACTIVE
        assert "updated_at" in body
        assert "deleted_at" not in body  # internal field excluded
    finally:
        _teardown()


def test_get_own_profile_requires_auth() -> None:
    app.dependency_overrides.clear()  # remove all overrides — real auth required
    client = TestClient(app, raise_server_exceptions=False)
    try:
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# PATCH /users/me
# ---------------------------------------------------------------------------


def test_patch_own_profile_updates_bio_and_privacy() -> None:
    client = _client(current_user=_ALICE)
    try:
        resp = client.patch(
            "/api/v1/users/me",
            json={"bio": "Updated bio", "is_private": True},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["bio"] == "Updated bio"
        assert body["is_private"] is True
    finally:
        _teardown()


def test_patch_own_profile_suspended_returns_403() -> None:
    client = _client(current_user=_SUSPENDED_USER)
    try:
        resp = client.patch("/api/v1/users/me", json={"bio": "nope"})
        assert resp.status_code == 403
        assert "suspended" in resp.json()["detail"].lower()
    finally:
        _teardown()


def test_patch_own_profile_pending_deletion_returns_403() -> None:
    client = _client(current_user=_PENDING_USER)
    try:
        resp = client.patch("/api/v1/users/me", json={"bio": "nope"})
        assert resp.status_code == 403
        assert "deletion" in resp.json()["detail"].lower()
    finally:
        _teardown()


# ---------------------------------------------------------------------------
# GET /users/{username} — public profile
# ---------------------------------------------------------------------------


def test_get_public_profile_returns_safe_fields_only() -> None:
    client = _client()
    try:
        resp = client.get("/api/v1/users/alice")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["username"] == "alice"
        # Private fields must NOT appear
        assert "email" not in body
        assert "status" not in body
        assert "updated_at" not in body
    finally:
        _teardown()


def test_get_public_profile_returns_404_for_unknown() -> None:
    client = _client()
    try:
        resp = client.get("/api/v1/users/nobody")
        assert resp.status_code == 404
    finally:
        _teardown()


def test_get_public_profile_returns_404_for_suspended_user() -> None:
    """Suspended accounts must not leak their existence to the public."""
    client = _client()
    try:
        resp = client.get("/api/v1/users/suspended_sam")
        assert resp.status_code == 404
    finally:
        _teardown()


def test_get_public_profile_returns_404_for_pending_deletion_user() -> None:
    """Pending-deletion accounts must not leak their existence to the public."""
    client = _client()
    try:
        resp = client.get("/api/v1/users/pending_pat")
        assert resp.status_code == 404
    finally:
        _teardown()
