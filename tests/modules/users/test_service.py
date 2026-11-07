import asyncio
from collections.abc import Coroutine
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.modules.users.models import User
from app.modules.users.repository import UserAlreadyExistsError
from app.modules.users.service import UserNotFoundError, UserService


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
            (user for user in self.users.values() if user.username == username),
            None,
        )

    async def get_by_email(self, email: str) -> User | None:
        return next(
            (user for user in self.users.values() if user.email == email),
            None,
        )


def run(coroutine: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coroutine)


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
    assert user.status == "active"
    assert repository.users[user_id] == user


def test_create_user_rejects_duplicate_username() -> None:
    repository = FakeUserRepository()
    service = UserService(repository, id_factory=uuid4)
    run(service.create_user(username="alice", email="one@example.com"))

    with pytest.raises(UserAlreadyExistsError, match="username"):
        run(service.create_user(username=" Alice ", email="two@example.com"))


def test_get_user_raises_for_unknown_id() -> None:
    service = UserService(FakeUserRepository())
    unknown_id = uuid4()

    with pytest.raises(UserNotFoundError, match=str(unknown_id)):
        run(service.get_user(unknown_id))
