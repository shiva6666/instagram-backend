"""Unit tests for UserService.

All tests use FakeUserRepository — no database, no I/O.
Tests cover:
  - create_user: normalization, duplicate username/email
  - get_user: missing user, hard-deleted user
  - get_public_profile: missing, suspended, pending-deletion, happy path
  - update_profile: happy path, forbidden (wrong actor), missing user,
                    suspended account, pending-deletion account
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.modules.users.models import User, UserStatus
from app.modules.users.repository import UserAlreadyExistsError
from app.modules.users.service import (
    ForbiddenError,
    UserNotFoundError,
    UserPendingDeletionError,
    UserService,
    UserSuspendedError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(coroutine: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coroutine)


def _make_user(
    *,
    user_id: UUID | None = None,
    username: str = "alice",
    email: str = "alice@example.com",
    status: str = UserStatus.ACTIVE,
    deleted_at: datetime | None = None,
) -> User:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return User(
        id=user_id or uuid4(),
        username=username,
        email=email,
        bio=None,
        avatar_key=None,
        is_private=False,
        status=status,
        created_at=now,
        updated_at=now,
        deleted_at=deleted_at,
    )


# ---------------------------------------------------------------------------
# In-memory fake repository
# ---------------------------------------------------------------------------


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def add(self, user: User) -> User:
        if any(
            existing.username == user.username or existing.email == user.email
            for existing in self.users.values()
        ):
            raise UserAlreadyExistsError
        self.users[user.id] = user
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_username(self, username: str) -> User | None:
        return next(
            (u for u in self.users.values() if u.username == username),
            None,
        )

    async def get_by_email(self, email: str) -> User | None:
        return next(
            (u for u in self.users.values() if u.email == email),
            None,
        )

    async def save(self, user: User) -> User:
        self.users[user.id] = user
        return user


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------


def test_create_user_normalizes_identity_fields() -> None:
    repository = FakeUserRepository()
    user_id = uuid4()
    service = UserService(repository, id_factory=lambda: user_id)

    user = run(
        service.create_user(
            username="  Alice  ",
            email=" Alice@Example.com ",
            bio="Hello",
        )
    )

    assert user.id == user_id
    assert user.username == "alice"
    assert user.email == "alice@example.com"
    assert user.status == UserStatus.ACTIVE
    assert user.avatar_key is None
    assert repository.users[user_id] == user


def test_create_user_rejects_duplicate_username() -> None:
    repository = FakeUserRepository()
    service = UserService(repository, id_factory=uuid4)
    run(service.create_user(username="alice", email="one@example.com"))

    with pytest.raises(UserAlreadyExistsError, match="username"):
        run(service.create_user(username=" Alice ", email="two@example.com"))


def test_create_user_rejects_duplicate_email() -> None:
    repository = FakeUserRepository()
    service = UserService(repository, id_factory=uuid4)
    run(service.create_user(username="alice", email="shared@example.com"))

    with pytest.raises(UserAlreadyExistsError, match="email"):
        run(service.create_user(username="bob", email=" Shared@Example.com "))


def test_create_user_rejects_blank_username() -> None:
    service = UserService(FakeUserRepository())
    with pytest.raises(ValueError, match="username"):
        run(service.create_user(username="   ", email="a@example.com"))


def test_create_user_rejects_blank_email() -> None:
    service = UserService(FakeUserRepository())
    with pytest.raises(ValueError, match="email"):
        run(service.create_user(username="alice", email="   "))


# ---------------------------------------------------------------------------
# get_user
# ---------------------------------------------------------------------------


def test_get_user_raises_for_unknown_id() -> None:
    service = UserService(FakeUserRepository())
    unknown_id = uuid4()
    with pytest.raises(UserNotFoundError, match=str(unknown_id)):
        run(service.get_user(unknown_id))


def test_get_user_raises_for_hard_deleted_user() -> None:
    """A user with deleted_at set is treated as not found."""
    repository = FakeUserRepository()
    deleted_user = _make_user(deleted_at=datetime(2026, 6, 1, tzinfo=UTC))
    repository.users[deleted_user.id] = deleted_user

    with pytest.raises(UserNotFoundError):
        run(service_with(repository).get_user(deleted_user.id))


# ---------------------------------------------------------------------------
# get_public_profile
# ---------------------------------------------------------------------------


def test_get_public_profile_returns_active_user() -> None:
    repository = FakeUserRepository()
    user = _make_user(username="alice")
    repository.users[user.id] = user

    result = run(service_with(repository).get_public_profile("alice"))
    assert result.username == "alice"


def test_get_public_profile_raises_for_unknown_username() -> None:
    service = UserService(FakeUserRepository())
    with pytest.raises(UserNotFoundError):
        run(service.get_public_profile("nobody"))


def test_get_public_profile_raises_404_for_suspended_user() -> None:
    """Suspended accounts must not be visible publicly — appear as 404."""
    repository = FakeUserRepository()
    user = _make_user(username="alice", status=UserStatus.SUSPENDED)
    repository.users[user.id] = user

    with pytest.raises(UserNotFoundError):
        run(service_with(repository).get_public_profile("alice"))


def test_get_public_profile_raises_404_for_pending_deletion_user() -> None:
    """Pending-deletion accounts must not be visible publicly — appear as 404."""
    repository = FakeUserRepository()
    user = _make_user(username="alice", status=UserStatus.PENDING_DELETION)
    repository.users[user.id] = user

    with pytest.raises(UserNotFoundError):
        run(service_with(repository).get_public_profile("alice"))


def test_get_public_profile_normalizes_username_lookup() -> None:
    """Username lookup is case-insensitive (normalized before query)."""
    repository = FakeUserRepository()
    user = _make_user(username="alice")
    repository.users[user.id] = user

    result = run(service_with(repository).get_public_profile("  ALICE  "))
    assert result.username == "alice"


# ---------------------------------------------------------------------------
# update_profile
# ---------------------------------------------------------------------------


def test_update_profile_changes_bio_and_privacy() -> None:
    repository = FakeUserRepository()
    user = _make_user()
    repository.users[user.id] = user

    updated = run(
        service_with(repository).update_profile(
            actor=user,
            target_user_id=user.id,
            bio="New bio",
            is_private=True,
        )
    )

    assert updated.bio == "New bio"
    assert updated.is_private is True
    assert updated.updated_at > user.updated_at


def test_update_profile_clears_bio_when_passed_none() -> None:
    repository = FakeUserRepository()
    user = _make_user()
    repository.users[user.id] = user

    updated = run(
        service_with(repository).update_profile(
            actor=user,
            target_user_id=user.id,
            bio=None,
        )
    )

    assert updated.bio is None


def test_update_profile_raises_forbidden_for_different_user() -> None:
    """An actor must not be able to update another user's profile."""
    repository = FakeUserRepository()
    alice = _make_user(username="alice")
    bob = _make_user(username="bob")
    repository.users[alice.id] = alice
    repository.users[bob.id] = bob

    with pytest.raises(ForbiddenError):
        run(
            service_with(repository).update_profile(
                actor=alice,
                target_user_id=bob.id,
                bio="Hacked bio",
            )
        )


def test_update_profile_raises_for_missing_user() -> None:
    """Target user must exist."""
    service = UserService(FakeUserRepository())
    ghost_id = uuid4()
    ghost = _make_user(user_id=ghost_id)

    with pytest.raises(UserNotFoundError):
        run(service.update_profile(actor=ghost, target_user_id=ghost_id, bio="x"))


def test_update_profile_raises_for_suspended_actor() -> None:
    repository = FakeUserRepository()
    user = _make_user(status=UserStatus.SUSPENDED)
    repository.users[user.id] = user

    with pytest.raises(UserSuspendedError):
        run(
            service_with(repository).update_profile(
                actor=user,
                target_user_id=user.id,
                bio="Won't work",
            )
        )


def test_update_profile_raises_for_pending_deletion_actor() -> None:
    repository = FakeUserRepository()
    user = _make_user(status=UserStatus.PENDING_DELETION)
    repository.users[user.id] = user

    with pytest.raises(UserPendingDeletionError):
        run(
            service_with(repository).update_profile(
                actor=user,
                target_user_id=user.id,
                bio="Won't work",
            )
        )


def test_update_profile_bumps_updated_at() -> None:
    repository = FakeUserRepository()
    user = _make_user()
    repository.users[user.id] = user
    original_updated_at = user.updated_at

    updated = run(
        service_with(repository).update_profile(
            actor=user,
            target_user_id=user.id,
            is_private=True,
        )
    )

    assert updated.updated_at > original_updated_at


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def service_with(repository: FakeUserRepository) -> UserService:
    return UserService(repository, id_factory=uuid4)
