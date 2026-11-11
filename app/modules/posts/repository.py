from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    and_,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from app.core.db import Base
from app.modules.posts.models import Post, PostImage


class PostRepository(Protocol):
    async def add(self, post: Post) -> Post: ...

    async def get_by_id(self, post_id: UUID) -> Post | None: ...

    async def list_by_author(
        self, author_id: UUID, *, offset: int, limit: int
    ) -> list[Post]: ...

    async def soft_delete(self, post_id: UUID, *, deleted_at: datetime) -> None: ...

    async def is_following(self, follower_id: UUID, followee_id: UUID) -> bool: ...

    async def is_blocked_between(self, first_user_id: UUID, second_user_id: UUID) -> bool: ...


class PostRow(Base):
    __tablename__ = "posts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    caption: Mapped[str | None] = mapped_column(String(2200), nullable=True)
    is_private: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    images: Mapped[list[PostImageRow]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostImageRow.position",
        lazy="selectin",
    )


class PostImageRow(Base):
    __tablename__ = "post_images"

    post_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    post: Mapped[PostRow] = relationship(back_populates="images")


class UserFollowRow(Base):
    """Minimal follow edge used by post visibility; follow APIs live in a later module."""

    __tablename__ = "user_follows"

    follower_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    followee_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class UserBlockRow(Base):
    """Minimal block edge used to prevent either side seeing the other's posts."""

    __tablename__ = "user_blocks"

    blocker_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    blocked_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )


def _to_domain(row: PostRow) -> Post:
    return Post(
        id=row.id,
        user_id=row.user_id,
        caption=row.caption,
        images=tuple(
            PostImage(position=image.position, url=image.url)
            for image in row.images
        ),
        is_private=row.is_private,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlAlchemyPostRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, post: Post) -> Post:
        row = PostRow(
            id=post.id,
            user_id=post.user_id,
            caption=post.caption,
            is_private=post.is_private,
            created_at=post.created_at,
            updated_at=post.updated_at,
            deleted_at=post.deleted_at,
            images=[
                PostImageRow(
                    post_id=post.id,
                    position=image.position,
                    url=image.url,
                )
                for image in post.images
            ],
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get_by_id(self, post_id: UUID) -> Post | None:
        row = await self._session.scalar(
            select(PostRow)
            .options(selectinload(PostRow.images))
            .where(PostRow.id == post_id, PostRow.deleted_at.is_(None))
        )
        return _to_domain(row) if row is not None else None

    async def list_by_author(
        self, author_id: UUID, *, offset: int, limit: int
    ) -> list[Post]:
        rows = (
            await self._session.scalars(
                select(PostRow)
                .options(selectinload(PostRow.images))
                .where(
                    PostRow.user_id == author_id,
                    PostRow.deleted_at.is_(None),
                )
                .order_by(PostRow.created_at.desc(), PostRow.id.desc())
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
        return [_to_domain(row) for row in rows]

    async def soft_delete(self, post_id: UUID, *, deleted_at: datetime) -> None:
        await self._session.execute(
            update(PostRow)
            .where(PostRow.id == post_id, PostRow.deleted_at.is_(None))
            .values(deleted_at=deleted_at, updated_at=deleted_at)
        )
        await self._session.flush()

    async def is_following(self, follower_id: UUID, followee_id: UUID) -> bool:
        result = await self._session.scalar(
            select(UserFollowRow.follower_id).where(
                UserFollowRow.follower_id == follower_id,
                UserFollowRow.followee_id == followee_id,
                UserFollowRow.status == "accepted",
            )
        )
        return result is not None

    async def is_blocked_between(
        self, first_user_id: UUID, second_user_id: UUID
    ) -> bool:
        result = await self._session.scalar(
            select(UserBlockRow.blocker_id).where(
                or_(
                    and_(
                        UserBlockRow.blocker_id == first_user_id,
                        UserBlockRow.blocked_id == second_user_id,
                    ),
                    and_(
                        UserBlockRow.blocker_id == second_user_id,
                        UserBlockRow.blocked_id == first_user_id,
                    ),
                )
            )
        )
        return result is not None
