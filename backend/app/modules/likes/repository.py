from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, delete, func, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class LikeRepository(Protocol):
    async def add(self, user_id: UUID, post_id: UUID, created_at: datetime) -> bool: ...

    async def remove(self, user_id: UUID, post_id: UUID) -> bool: ...

    async def count_for_post(self, post_id: UUID) -> int: ...

    async def exists(self, user_id: UUID, post_id: UUID) -> bool: ...


class LikeRow(Base):
    __tablename__ = "post_likes"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    post_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SqlAlchemyLikeRepository:
    """PostgreSQL adapter for user-to-post like relationships."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: UUID, post_id: UUID, created_at: datetime) -> bool:
        statement = (
            pg_insert(LikeRow)
            .values(user_id=user_id, post_id=post_id, created_at=created_at)
            .on_conflict_do_nothing(
                index_elements=[LikeRow.user_id, LikeRow.post_id]
            )
            .returning(LikeRow.user_id)
        )
        inserted_user_id = await self._session.scalar(statement)
        return inserted_user_id is not None

    async def remove(self, user_id: UUID, post_id: UUID) -> bool:
        result = await self._session.execute(
            delete(LikeRow).where(
                LikeRow.user_id == user_id,
                LikeRow.post_id == post_id,
            )
        )
        return result.rowcount > 0

    async def count_for_post(self, post_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count()).select_from(LikeRow).where(LikeRow.post_id == post_id)
        )
        return int(count or 0)

    async def exists(self, user_id: UUID, post_id: UUID) -> bool:
        result = await self._session.scalar(
            select(LikeRow.user_id).where(
                LikeRow.user_id == user_id,
                LikeRow.post_id == post_id,
            )
        )
        return result is not None
