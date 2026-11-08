from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import ColumnElement

from app.core.db import Base
from app.modules.auth.models import AuthIdentity, RefreshToken
from app.modules.users.models import User
from app.modules.users.repository import UserRow, _to_domain


class AuthRepository(Protocol):
    async def add_identity(self, identity: AuthIdentity) -> AuthIdentity: ...

    async def get_identity_by_email(
        self, email: str
    ) -> tuple[AuthIdentity, User] | None: ...

    async def get_identity_by_user_id(
        self, user_id: UUID
    ) -> tuple[AuthIdentity, User] | None: ...

    async def add_refresh_token(self, token: RefreshToken) -> None: ...

    async def get_refresh_token_for_update(
        self, token_hash: str
    ) -> RefreshToken | None: ...

    async def rotate_refresh_token(
        self, old_token_id: UUID, consumed_at: datetime, new_token: RefreshToken
    ) -> None: ...

    async def revoke_refresh_family(
        self, family_id: UUID, revoked_at: datetime
    ) -> None: ...

    async def revoke_refresh_token_hash(
        self, token_hash: str, revoked_at: datetime
    ) -> UUID | None: ...


class AuthIdentityRow(Base):
    __tablename__ = "auth_identities"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RefreshTokenRow(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    family_id: Mapped[UUID] = mapped_column(nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_token_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.id")
    )


def _to_identity(row: AuthIdentityRow) -> AuthIdentity:
    return AuthIdentity(
        id=row.id,
        user_id=row.user_id,
        provider=row.provider,
        provider_subject=row.provider_subject,
        password_hash=row.password_hash,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_refresh_token(row: RefreshTokenRow) -> RefreshToken:
    return RefreshToken(
        id=row.id,
        user_id=row.user_id,
        family_id=row.family_id,
        token_hash=row.token_hash,
        created_at=row.created_at,
        expires_at=row.expires_at,
        consumed_at=row.consumed_at,
        revoked_at=row.revoked_at,
        replaced_by_token_id=row.replaced_by_token_id,
    )


class SqlAlchemyAuthRepository:
    """PostgreSQL adapter for authentication identities and refresh sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_identity(self, identity: AuthIdentity) -> AuthIdentity:
        row = AuthIdentityRow(
            id=identity.id,
            user_id=identity.user_id,
            provider=identity.provider,
            provider_subject=identity.provider_subject,
            password_hash=identity.password_hash,
            created_at=identity.created_at,
            updated_at=identity.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_identity(row)

    async def _identity_query(
        self, condition: ColumnElement[bool]
    ) -> tuple[AuthIdentity, User] | None:
        result = await self._session.execute(
            select(AuthIdentityRow, UserRow)
            .join(UserRow, UserRow.id == AuthIdentityRow.user_id)
            .where(condition)
        )
        row = result.one_or_none()
        if row is None:
            return None
        identity_row, user_row = row
        return _to_identity(identity_row), _to_domain(user_row)

    async def get_identity_by_email(self, email: str) -> tuple[AuthIdentity, User] | None:
        return await self._identity_query(
            (AuthIdentityRow.provider == "password")
            & (AuthIdentityRow.provider_subject == email)
        )

    async def get_identity_by_user_id(
        self, user_id: UUID
    ) -> tuple[AuthIdentity, User] | None:
        return await self._identity_query(
            (AuthIdentityRow.provider == "password")
            & (AuthIdentityRow.user_id == user_id)
        )

    async def add_refresh_token(self, token: RefreshToken) -> None:
        self._session.add(
            RefreshTokenRow(
                id=token.id,
                user_id=token.user_id,
                family_id=token.family_id,
                token_hash=token.token_hash,
                created_at=token.created_at,
                expires_at=token.expires_at,
                consumed_at=token.consumed_at,
                revoked_at=token.revoked_at,
                replaced_by_token_id=token.replaced_by_token_id,
            )
        )
        await self._session.flush()

    async def get_refresh_token_for_update(self, token_hash: str) -> RefreshToken | None:
        row = await self._session.scalar(
            select(RefreshTokenRow)
            .where(RefreshTokenRow.token_hash == token_hash)
            .with_for_update()
        )
        return _to_refresh_token(row) if row is not None else None

    async def rotate_refresh_token(
        self, old_token_id: UUID, consumed_at: datetime, new_token: RefreshToken
    ) -> None:
        result = await self._session.execute(
            update(RefreshTokenRow)
            .where(
                RefreshTokenRow.id == old_token_id,
                RefreshTokenRow.consumed_at.is_(None),
                RefreshTokenRow.revoked_at.is_(None),
            )
            .values(consumed_at=consumed_at, replaced_by_token_id=new_token.id)
        )
        if result.rowcount != 1:
            raise RuntimeError("refresh token was concurrently consumed")
        await self.add_refresh_token(new_token)

    async def revoke_refresh_family(self, family_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(RefreshTokenRow)
            .where(
                RefreshTokenRow.family_id == family_id,
                RefreshTokenRow.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def revoke_refresh_token_hash(
        self, token_hash: str, revoked_at: datetime
    ) -> UUID | None:
        token = await self._session.scalar(
            select(RefreshTokenRow)
            .where(RefreshTokenRow.token_hash == token_hash)
            .with_for_update()
        )
        if token is None:
            return None
        await self.revoke_refresh_family(token.family_id, revoked_at)
        return token.user_id
