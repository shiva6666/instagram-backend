from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from anyio import to_thread
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings
from app.core.ids import new_uuid7
from app.modules.auth.models import AuthIdentity, RefreshToken
from app.modules.auth.repository import AuthRepository
from app.modules.auth.tokens import create_access_token, create_refresh_token, hash_refresh_token
from app.modules.users.models import User
from app.modules.users.repository import UserAlreadyExistsError, UserRepository
from app.modules.users.service import UserService


class InvalidCredentialsError(ValueError):
    """Credentials are invalid or the account cannot authenticate."""


class InvalidRefreshTokenError(ValueError):
    """Refresh token is unknown, expired, or revoked."""


class RefreshTokenReuseError(InvalidRefreshTokenError):
    """A refresh token that was already consumed has been presented again."""


class AuthService:
    def __init__(
        self, auth_repository: AuthRepository, user_repository: UserRepository
    ) -> None:
        self._auth_repository = auth_repository
        self._user_service = UserService(user_repository)
        self._password_hasher = PasswordHasher()

    async def register(
        self, *, username: str, email: str, password: str,
        bio: str | None = None, is_private: bool = False,
    ) -> tuple[User, str, str]:
        normalized_email = email.strip().lower()
        user = await self._user_service.create_user(
            username=username, email=normalized_email, bio=bio, is_private=is_private
        )
        now = datetime.now(UTC)
        identity = AuthIdentity(
            id=new_uuid7(), user_id=user.id, provider="password",
            provider_subject=normalized_email,
            password_hash=await to_thread.run_sync(self._password_hasher.hash, password),
            created_at=now, updated_at=now,
        )
        await self._auth_repository.add_identity(identity)
        access_token, refresh_token = await self._issue_tokens(user)
        return user, access_token, refresh_token

    async def login(self, *, email: str, password: str) -> tuple[User, str, str]:
        account = await self._auth_repository.get_identity_by_email(email.strip().lower())
        if account is None:
            raise InvalidCredentialsError("email or password is incorrect")
        identity, user = account
        try:
            valid = await to_thread.run_sync(
                self._password_hasher.verify, identity.password_hash, password
            )
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            valid = False
        if not valid or user.status != "active" or user.deleted_at is not None:
            raise InvalidCredentialsError("email or password is incorrect")
        access_token, refresh_token = await self._issue_tokens(user)
        return user, access_token, refresh_token

    async def refresh(self, raw_token: str) -> tuple[User, str, str]:
        now = datetime.now(UTC)
        stored = await self._auth_repository.get_refresh_token_for_update(
            hash_refresh_token(raw_token)
        )
        if stored is None:
            raise InvalidRefreshTokenError("refresh token is invalid")
        if stored.consumed_at is not None:
            await self._auth_repository.revoke_refresh_family(stored.family_id, now)
            raise RefreshTokenReuseError("refresh token reuse detected")
        if stored.revoked_at is not None or stored.expires_at <= now:
            raise InvalidRefreshTokenError("refresh token is expired or revoked")

        account = await self._auth_repository.get_identity_by_user_id(stored.user_id)
        if account is None:
            await self._auth_repository.revoke_refresh_family(stored.family_id, now)
            raise InvalidRefreshTokenError("account is unavailable")
        _, user = account
        if user.status != "active" or user.deleted_at is not None:
            await self._auth_repository.revoke_refresh_family(stored.family_id, now)
            raise InvalidRefreshTokenError("account is unavailable")

        raw_successor = create_refresh_token()
        successor = self._new_refresh_token(user.id, stored.family_id, raw_successor, now)
        await self._auth_repository.rotate_refresh_token(stored.id, now, successor)
        return user, create_access_token(user.id), raw_successor

    async def logout(self, raw_token: str) -> None:
        await self._auth_repository.revoke_refresh_token_hash(
            hash_refresh_token(raw_token), datetime.now(UTC)
        )

    async def _issue_tokens(self, user: User) -> tuple[str, str]:
        now = datetime.now(UTC)
        raw_refresh = create_refresh_token()
        await self._auth_repository.add_refresh_token(
            self._new_refresh_token(user.id, new_uuid7(), raw_refresh, now)
        )
        return create_access_token(user.id), raw_refresh

    @staticmethod
    def _new_refresh_token(
        user_id: UUID, family_id: UUID, raw_token: str, now: datetime
    ) -> RefreshToken:
        return RefreshToken(
            id=new_uuid7(), user_id=user_id, family_id=family_id,
            token_hash=hash_refresh_token(raw_token), created_at=now,
            expires_at=now + timedelta(days=settings.auth_refresh_token_ttl_days),
        )
