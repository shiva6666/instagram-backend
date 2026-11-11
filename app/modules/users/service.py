from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from app.core.ids import new_uuid7
from app.modules.users.models import User, UserStatus
from app.modules.users.repository import UserAlreadyExistsError, UserRepository

# Re-export so callers only need to import from the service layer.
__all__ = [
    "ForbiddenError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "UserPendingDeletionError",
    "UserService",
    "UserSuspendedError",
]

_SENTINEL = object()  # used to distinguish "not provided" from None


class UserNotFoundError(LookupError):
    """Raised when a requested user does not exist or has been hard-deleted."""


class UserSuspendedError(PermissionError):
    """Raised when an operation is attempted on a suspended account."""


class UserPendingDeletionError(PermissionError):
    """Raised when an operation is attempted on an account pending deletion."""


class ForbiddenError(PermissionError):
    """Raised when an authenticated user tries to modify another user's data."""


def _assert_account_operable(user: User) -> None:
    """Raise a typed exception if the account cannot perform actions.

    Rules
    -----
    - ``suspended``       → raises UserSuspendedError
    - ``pending_deletion`` → raises UserPendingDeletionError
    - Hard-deleted (deleted_at set) is treated the same as not found upstream;
      this guard is here as a safety net.
    """
    if user.status == UserStatus.SUSPENDED:
        raise UserSuspendedError(f"account {user.id} is suspended")
    if user.status == UserStatus.PENDING_DELETION:
        raise UserPendingDeletionError(
            f"account {user.id} is pending deletion"
        )


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        id_factory: Callable[[], UUID] = new_uuid7,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_user(self, user_id: UUID) -> User:
        """Return a user by ID.  Raises UserNotFoundError when absent."""
        user = await self._repository.get_by_id(user_id)
        if user is None or user.deleted_at is not None:
            raise UserNotFoundError(f"user {user_id} was not found")
        return user

    async def get_public_profile(self, username: str) -> User:
        """Return a user by username for public profile display.

        Suspended and pending-deletion accounts are not visible publicly;
        callers receive UserNotFoundError so we do not leak account status.
        """
        user = await self._repository.get_by_username(username.strip().lower())
        if user is None or user.deleted_at is not None:
            raise UserNotFoundError(f"user '{username}' was not found")
        # Suspended / pending-deletion accounts appear as not-found to the
        # outside world to avoid leaking that the username exists.
        if user.status != UserStatus.ACTIVE:
            raise UserNotFoundError(f"user '{username}' was not found")
        return user

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

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
                avatar_key=None,
                is_private=is_private,
                status=UserStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
        )

    async def update_profile(
        self,
        *,
        actor: User,
        target_user_id: UUID,
        bio: object = _SENTINEL,
        is_private: object = _SENTINEL,
    ) -> User:
        """Update editable profile fields for *target_user_id*.

        Parameters
        ----------
        actor:
            The currently authenticated user performing the update.
        target_user_id:
            The user whose profile is being modified.
        bio:
            New bio value.  Pass ``_SENTINEL`` (the default) to leave
            unchanged.  Pass ``None`` explicitly to clear the bio.
        is_private:
            New privacy setting.  Pass ``_SENTINEL`` to leave unchanged.

        Raises
        ------
        ForbiddenError
            When ``actor.id != target_user_id``.
        UserNotFoundError
            When the target account does not exist or is hard-deleted.
        UserSuspendedError / UserPendingDeletionError
            When the actor's account is not operable.
        """
        if actor.id != target_user_id:
            raise ForbiddenError("you may only edit your own profile")

        # Re-fetch to get the freshest snapshot (the actor object comes from
        # the JWT dependency and may be slightly stale).
        user = await self.get_user(target_user_id)
        _assert_account_operable(user)

        updates: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if bio is not _SENTINEL:
            updates["bio"] = bio
        if is_private is not _SENTINEL:
            updates["is_private"] = is_private

        updated = replace(user, **updates)  # type: ignore[arg-type]
        return await self._repository.save(updated)
