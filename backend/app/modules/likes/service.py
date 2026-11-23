from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.modules.likes.models import LikeStatus
from app.modules.likes.repository import LikeRepository
from app.modules.posts.service import PostService
from app.modules.users.models import User


class LikeService:
    def __init__(self, likes: LikeRepository, posts: PostService) -> None:
        self._likes = likes
        self._posts = posts

    async def _assert_post_visible(self, *, post_id: UUID, actor: User) -> None:
        # Reuse the post module's visibility rules. This covers deleted posts,
        # private accounts, private posts, and blocks in either direction.
        await self._posts.get_post(post_id=post_id, viewer=actor)

    async def _status(self, *, post_id: UUID, actor: User) -> LikeStatus:
        liked = await self._likes.exists(actor.id, post_id)
        like_count = await self._likes.count_for_post(post_id)
        return LikeStatus(post_id=post_id, liked=liked, like_count=like_count)

    async def get_status(self, *, post_id: UUID, actor: User) -> LikeStatus:
        await self._assert_post_visible(post_id=post_id, actor=actor)
        return await self._status(post_id=post_id, actor=actor)

    async def like(self, *, post_id: UUID, actor: User) -> LikeStatus:
        await self._assert_post_visible(post_id=post_id, actor=actor)
        await self._likes.add(actor.id, post_id, datetime.now(UTC))
        # INSERT .. ON CONFLICT DO NOTHING makes repeated/concurrent likes safe.
        return await self._status(post_id=post_id, actor=actor)

    async def unlike(self, *, post_id: UUID, actor: User) -> LikeStatus:
        await self._assert_post_visible(post_id=post_id, actor=actor)
        await self._likes.remove(actor.id, post_id)
        # DELETE is naturally idempotent: an already absent like stays absent.
        return await self._status(post_id=post_id, actor=actor)
