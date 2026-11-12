from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.follows.models import (
    FollowRelationship,
    FollowStatus,
    FollowedUser,
)
from app.modules.social_graph.tables import FollowRow
from app.modules.users.models import User
from app.modules.users.repository import UserRow, _to_domain


class FollowRepository(Protocol):
    async def get_relationship(
        self, follower_id: UUID, following_id: UUID
    ) -> FollowRelationship | None: ...

    async def add_relationship(
        self, follower_id: UUID, following_id: UUID, status: str, created_at: datetime
    ) -> FollowRelationship: ...

    async def remove_relationship(
        self, follower_id: UUID, following_id: UUID, *, pending_only: bool = False
    ) -> bool: ...

    async def accept_request(
        self, follower_id: UUID, following_id: UUID
    ) -> FollowRelationship | None: ...

    async def list_followers(
        self,
        user_id: UUID,
        *,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[FollowedUser]: ...

    async def list_following(
        self,
        user_id: UUID,
        *,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[FollowedUser]: ...

    async def count_followers(self, user_id: UUID) -> int: ...

    async def count_following(self, user_id: UUID) -> int: ...


def _to_relationship(row: FollowRow) -> FollowRelationship:
    return FollowRelationship(
        follower_id=row.follower_id,
        following_id=row.following_id,
        status=row.status,
        created_at=row.created_at,
    )


class SqlAlchemyFollowRepository:
    """PostgreSQL adapter for follow relationships."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_relationship(
        self, follower_id: UUID, following_id: UUID
    ) -> FollowRelationship | None:
        row = await self._session.scalar(
            select(FollowRow).where(
                FollowRow.follower_id == follower_id,
                FollowRow.following_id == following_id,
            )
        )
        return _to_relationship(row) if row is not None else None

    async def add_relationship(
        self, follower_id: UUID, following_id: UUID, status: str, created_at: datetime
    ) -> FollowRelationship:
        statement = (
            pg_insert(FollowRow)
            .values(
                follower_id=follower_id,
                following_id=following_id,
                status=status,
                created_at=created_at,
            )
            .on_conflict_do_nothing(
                index_elements=[FollowRow.follower_id, FollowRow.following_id]
            )
        )
        await self._session.execute(statement)
        relationship = await self.get_relationship(follower_id, following_id)
        if relationship is None:
            raise RuntimeError("follow relationship could not be persisted")
        return relationship

    async def remove_relationship(
        self, follower_id: UUID, following_id: UUID, *, pending_only: bool = False
    ) -> bool:
        statement = delete(FollowRow).where(
            FollowRow.follower_id == follower_id,
            FollowRow.following_id == following_id,
        )
        if pending_only:
            statement = statement.where(FollowRow.status == FollowStatus.PENDING)
        result = await self._session.execute(statement)
        return result.rowcount > 0

    async def accept_request(
        self, follower_id: UUID, following_id: UUID
    ) -> FollowRelationship | None:
        await self._session.execute(
            update(FollowRow)
            .where(
                FollowRow.follower_id == follower_id,
                FollowRow.following_id == following_id,
                FollowRow.status == FollowStatus.PENDING,
            )
            .values(status=FollowStatus.ACCEPTED)
        )
        return await self.get_relationship(follower_id, following_id)

    async def _list(
        self,
        *,
        user_id: UUID,
        followers: bool,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[FollowedUser]:
        user_column = FollowRow.follower_id if followers else FollowRow.following_id
        owner_column = FollowRow.following_id if followers else FollowRow.follower_id
        conditions = [
            owner_column == user_id,
            FollowRow.status == FollowStatus.ACCEPTED,
            UserRow.status == "active",
            UserRow.deleted_at.is_(None),
        ]
        if cursor is not None:
            cursor_time, cursor_user_id = cursor
            conditions.append(
                or_(
                    FollowRow.created_at < cursor_time,
                    and_(
                        FollowRow.created_at == cursor_time,
                        user_column < cursor_user_id,
                    ),
                )
            )

        rows = (
            await self._session.execute(
                select(FollowRow, UserRow)
                .join(UserRow, UserRow.id == user_column)
                .where(*conditions)
                .order_by(FollowRow.created_at.desc(), user_column.desc())
                .limit(limit + 1)
            )
        ).all()
        from app.modules.users.repository import _to_domain

        return [
            FollowedUser(user=_to_domain(user_row), followed_at=follow_row.created_at)
            for follow_row, user_row in rows
        ]

    async def list_followers(
        self,
        user_id: UUID,
        *,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[FollowedUser]:
        return await self._list(
            user_id=user_id, followers=True, cursor=cursor, limit=limit
        )

    async def list_following(
        self,
        user_id: UUID,
        *,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[FollowedUser]:
        return await self._list(
            user_id=user_id, followers=False, cursor=cursor, limit=limit
        )

    async def count_followers(self, user_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(FollowRow)
            .join(UserRow, UserRow.id == FollowRow.follower_id)
            .where(
                FollowRow.following_id == user_id,
                FollowRow.status == FollowStatus.ACCEPTED,
                UserRow.status == "active",
                UserRow.deleted_at.is_(None),
            )
        )
        return int(count or 0)

    async def count_following(self, user_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(FollowRow)
            .join(UserRow, UserRow.id == FollowRow.following_id)
            .where(
                FollowRow.follower_id == user_id,
                FollowRow.status == FollowStatus.ACCEPTED,
                UserRow.status == "active",
                UserRow.deleted_at.is_(None),
            )
        )
        return int(count or 0)
