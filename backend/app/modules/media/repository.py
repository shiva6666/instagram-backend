from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    bindparam,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.media.models import Media


class MediaRepository(Protocol):
    async def add(self, media: Media) -> Media: ...

    async def get_by_id(self, media_id: UUID) -> Media | None: ...

    async def get_by_id_for_update(self, media_id: UUID) -> Media | None: ...

    async def get_by_ids(self, media_ids: list[UUID]) -> list[Media]: ...

    async def get_by_ids_for_update(self, media_ids: list[UUID]) -> list[Media]: ...

    async def get_attached_ids(self, media_ids: list[UUID]) -> set[UUID]: ...

    async def save(self, media: Media) -> Media: ...


class MediaRow(Base):
    __tablename__ = "media"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    expected_size_bytes: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    height: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    display_object_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    thumbnail_object_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    upload_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cleanup_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _to_domain(row: MediaRow) -> Media:
    return Media(
        id=row.id,
        owner_id=row.owner_id,
        object_key=row.object_key,
        url=row.url,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        status=row.status,
        width=row.width,
        height=row.height,
        created_at=row.created_at,
        updated_at=row.updated_at,
        expected_size_bytes=row.expected_size_bytes,
        upload_expires_at=row.upload_expires_at,
        display_object_key=row.display_object_key,
        thumbnail_object_key=row.thumbnail_object_key,
        cleanup_requested_at=row.cleanup_requested_at,
        failure_reason=row.failure_reason,
    )


class SqlAlchemyMediaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, media: Media) -> Media:
        row = MediaRow(
            id=media.id,
            owner_id=media.owner_id,
            object_key=media.object_key,
            url=media.url,
            content_type=media.content_type,
            size_bytes=media.size_bytes,
            status=media.status,
            width=media.width,
            height=media.height,
            expected_size_bytes=media.expected_size_bytes,
            upload_expires_at=media.upload_expires_at,
            display_object_key=media.display_object_key,
            thumbnail_object_key=media.thumbnail_object_key,
            cleanup_requested_at=media.cleanup_requested_at,
            failure_reason=media.failure_reason,
            created_at=media.created_at,
            updated_at=media.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get_by_id(self, media_id: UUID) -> Media | None:
        row = await self._session.get(MediaRow, media_id)
        return _to_domain(row) if row is not None else None

    async def get_by_id_for_update(self, media_id: UUID) -> Media | None:
        row = await self._session.scalar(
            select(MediaRow).where(MediaRow.id == media_id).with_for_update()
        )
        return _to_domain(row) if row is not None else None

    async def get_by_ids(self, media_ids: list[UUID]) -> list[Media]:
        if not media_ids:
            return []
        rows = (
            await self._session.scalars(
                select(MediaRow).where(MediaRow.id.in_(media_ids))
            )
        ).all()
        return [_to_domain(row) for row in rows]

    async def get_by_ids_for_update(self, media_ids: list[UUID]) -> list[Media]:
        if not media_ids:
            return []
        rows = (
            await self._session.scalars(
                select(MediaRow)
                .where(MediaRow.id.in_(media_ids))
                .order_by(MediaRow.id)
                .with_for_update()
            )
        ).all()
        return [_to_domain(row) for row in rows]

    async def get_attached_ids(self, media_ids: list[UUID]) -> set[UUID]:
        if not media_ids:
            return set()
        statement = text(
            "SELECT media_id FROM post_media WHERE media_id IN :media_ids"
        ).bindparams(bindparam("media_ids", expanding=True))
        rows = (
            await self._session.execute(statement, {"media_ids": media_ids})
        ).scalars()
        return set(rows)

    async def save(self, media: Media) -> Media:
        await self._session.execute(
            update(MediaRow)
            .where(MediaRow.id == media.id)
            .values(
                object_key=media.object_key,
                url=media.url,
                content_type=media.content_type,
                size_bytes=media.size_bytes,
                status=media.status,
                width=media.width,
                height=media.height,
                expected_size_bytes=media.expected_size_bytes,
                upload_expires_at=media.upload_expires_at,
                display_object_key=media.display_object_key,
                thumbnail_object_key=media.thumbnail_object_key,
                cleanup_requested_at=media.cleanup_requested_at,
                failure_reason=media.failure_reason,
                updated_at=media.updated_at,
            )
        )
        await self._session.flush()
        return media
