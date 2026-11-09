from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import DateTime, String, select, update
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.users.models import User


class UserAlreadyExistsError(ValueError):
    """Raised when a username or email is already in use."""


class UserRepository(Protocol):
    async def add(self, user: User) -> User: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_username(self, username: str) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def save(self, user: User) -> User: ...


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    bio: Mapped[str | None]
    avatar_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_private: Mapped[bool] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def _to_domain(row: UserRow) -> User:
    return User(
        id=row.id,
        username=row.username,
        email=row.email,
        bio=row.bio,
        avatar_key=row.avatar_key,
        is_private=row.is_private,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlAlchemyUserRepository:
    """Persistence adapter for users; services depend on UserRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> User:
        row = UserRow(
            id=user.id,
            username=user.username,
            email=user.email,
            bio=user.bio,
            avatar_key=user.avatar_key,
            is_private=user.is_private,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            deleted_at=user.deleted_at,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as error:
            await self._session.rollback()
            raise UserAlreadyExistsError from error
        return _to_domain(row)

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.scalar(select(UserRow).where(UserRow.id == user_id))
        return _to_domain(row) if row is not None else None

    async def get_by_username(self, username: str) -> User | None:
        row = await self._session.scalar(
            select(UserRow).where(UserRow.username == username)
        )
        return _to_domain(row) if row is not None else None

    async def get_by_email(self, email: str) -> User | None:
        row = await self._session.scalar(select(UserRow).where(UserRow.email == email))
        return _to_domain(row) if row is not None else None

    async def save(self, user: User) -> User:
        """Persist a mutated domain entity back to the database.

        Uses an UPDATE statement targeting only the mutable profile columns so
        that the method is safe to call even if the caller only changed one
        field.  The caller is responsible for setting ``updated_at`` before
        passing the entity in.
        """
        await self._session.execute(
            update(UserRow)
            .where(UserRow.id == user.id)
            .values(
                bio=user.bio,
                avatar_key=user.avatar_key,
                is_private=user.is_private,
                status=user.status,
                updated_at=user.updated_at,
                deleted_at=user.deleted_at,
            )
        )
        await self._session.flush()
        return user
