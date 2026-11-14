from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.feed.models import FeedAuthor, FeedItem
from app.modules.posts.models import Post, PostImage


class FeedRepository(Protocol):
    async def list_feed(
        self,
        viewer_id: UUID,
        *,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[FeedItem]: ...


class SqlAlchemyFeedRepository:
    """PostgreSQL read adapter for the chronological home feed.

    The candidate query is set-based: one query selects eligible posts from
    the viewer and accepted followees. A second query batch-loads image rows.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_feed(
        self,
        viewer_id: UUID,
        *,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[FeedItem]:
        cursor_clause = ""
        params: dict[str, object] = {
            "viewer_id": viewer_id,
            "limit": limit + 1,
        }
        if cursor is not None:
            cursor_clause = """
                AND (
                    p.created_at < :cursor_created_at
                    OR (
                        p.created_at = :cursor_created_at
                        AND p.id < :cursor_post_id
                    )
                )
            """
            params["cursor_created_at"] = cursor[0]
            params["cursor_post_id"] = cursor[1]

        statement = text(
            f"""
            SELECT
                p.id AS post_id,
                p.user_id AS author_id,
                p.caption,
                p.is_private AS post_is_private,
                p.created_at,
                p.updated_at,
                p.deleted_at,
                u.username,
                u.avatar_key
            FROM posts AS p
            JOIN users AS u ON u.id = p.user_id
            WHERE
                p.deleted_at IS NULL
                AND u.deleted_at IS NULL
                AND u.status = 'active'
                AND (
                    p.user_id = :viewer_id
                    OR EXISTS (
                        SELECT 1
                        FROM follows AS f
                        WHERE
                            f.follower_id = :viewer_id
                            AND f.following_id = p.user_id
                            AND f.status = 'accepted'
                    )
                )
                AND (
                    p.user_id = :viewer_id
                    OR p.is_private IS FALSE
                )
                AND (
                    p.user_id = :viewer_id
                    OR NOT EXISTS (
                        SELECT 1
                        FROM user_blocks AS b
                        WHERE
                            (b.blocker_id = :viewer_id AND b.blocked_id = p.user_id)
                            OR
                            (b.blocker_id = p.user_id AND b.blocked_id = :viewer_id)
                    )
                )
                {cursor_clause}
            ORDER BY p.created_at DESC, p.id DESC
            LIMIT :limit
            """
        )
        rows = (await self._session.execute(statement, params)).mappings().all()

        if not rows:
            return []

        post_ids = [row["post_id"] for row in rows]
        image_statement = text(
            """
            SELECT post_id, position, url
            FROM post_images
            WHERE post_id IN :post_ids
            ORDER BY post_id, position
            """
        ).bindparams(bindparam("post_ids", expanding=True))
        image_rows = (
            await self._session.execute(image_statement, {"post_ids": post_ids})
        ).mappings().all()

        images_by_post: dict[UUID, list[PostImage]] = {
            post_id: [] for post_id in post_ids
        }
        for image_row in image_rows:
            images_by_post[image_row["post_id"]].append(
                PostImage(position=image_row["position"], url=image_row["url"])
            )

        return [
            FeedItem(
                post=Post(
                    id=row["post_id"],
                    user_id=row["author_id"],
                    caption=row["caption"],
                    images=tuple(images_by_post[row["post_id"]]),
                    is_private=row["post_is_private"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    deleted_at=row["deleted_at"],
                ),
                author=FeedAuthor(
                    id=row["author_id"],
                    username=row["username"],
                    avatar_key=row["avatar_key"],
                ),
            )
            for row in rows
        ]
