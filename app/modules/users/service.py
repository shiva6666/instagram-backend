from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from app.core.ids import new_uuid7
from app.modules.users.models import User
from app.modules.users.repository import UserAlreadyExistsError, UserRepository


class UserNotFoundError(LookupError):
    """Raised when a requested user does not exist."""


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        id_factory: Callable[[], UUID] = new_uuid7,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        bio: str | None = None,
        is_private: bool = False,
    ) -> User:
        normalized_username = username.strip().lower()
        normalized_email = email.strip().lower()
        if not normalized_username:
            raise ValueError("username must not be empty")
        if not normalized_email:
            raise ValueError("email must not be empty")

        if await self._repository.get_by_username(normalized_username) is not None:
            raise UserAlreadyExistsError("username is already in use")
        if await self._repository.get_by_email(normalized_email) is not None:
            raise UserAlreadyExistsError("email is already in use")

        now = datetime.now(UTC)
        return await self._repository.add(
            User(
                id=self._id_factory(),
                username=normalized_username,
                email=normalized_email,
                bio=bio,
                is_private=is_private,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )

    async def get_user(self, user_id: UUID) -> User:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"user {user_id} was not found")
        return user
