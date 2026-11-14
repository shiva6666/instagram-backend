from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from uuid import UUID

from app.core.ids import new_uuid7
from app.modules.posts.models import Post, PostImage, PostLifecycle, PostVisibility
from app.modules.posts.repository import PostRepository
from app.modules.users.models import User, UserStatus
from app.modules.users.repository import UserRepository


class PostNotFoundError(LookupError):
    """Raised when a post or author is unavailable."""


class PostForbiddenError(PermissionError):
    """Raised when the caller is not allowed to perform an operation."""


class UserUnavailableError(PermissionError):
    """Raised when the acting user's account cannot create or delete posts."""


class InvalidPostCursorError(ValueError):
    """Raised when an author-post cursor is malformed."""


def _encode_post_cursor(post: Post) -> str:
    payload = {
        "created_at": post.created_at.isoformat(),
        "post_id": str(post.id),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_post_cursor(cursor: str | None) -> tuple[datetime, UUID] | None:
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        created_at = datetime.fromisoformat(payload["created_at"])
        post_id = UUID(payload["post_id"])
        if created_at.tzinfo is None:
            raise ValueError("cursor timestamp must include timezone")
        return created_at, post_id
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise InvalidPostCursorError("invalid post cursor") from error


def _ensure_active(user: User) -> None:
    if user.deleted_at is not None or user.status != UserStatus.ACTIVE:
        raise UserUnavailableError("account is not allowed to perform this action")


class PostService:
    def __init__(
        self,
        posts: PostRepository,
        users: UserRepository,
    ) -> None:
        self._posts = posts
        self._users = users

    async def _active_author(self, user_id: UUID) -> User:
        author = await self._users.get_by_id(user_id)
        if author is None or author.deleted_at is not None:
            raise PostNotFoundError("author was not found")
        if author.status != UserStatus.ACTIVE:
            raise PostNotFoundError("author was not found")
        return author

    async def _assert_not_blocked(self, viewer_id: UUID, author_id: UUID) -> None:
        if viewer_id != author_id and await self._posts.is_blocked_between(
            viewer_id, author_id
        ):
            raise PostNotFoundError("post was not found")

    async def _assert_author_visible(self, viewer_id: UUID, author: User) -> None:
        await self._assert_not_blocked(viewer_id, author.id)
        if (
            author.is_private
            and viewer_id != author.id
            and not await self._posts.is_following(viewer_id, author.id)
        ):
            raise PostNotFoundError("author was not found")

    @staticmethod
    def _is_visible_to(post: Post, *, viewer_id: UUID) -> bool:
        if post.lifecycle != PostLifecycle.PUBLISHED:
            return False
        if viewer_id == post.user_id:
            return True
        return post.visibility != PostVisibility.PRIVATE

    async def create_post(
        self,
        *,
        actor: User,
        caption: str | None,
        image_urls: list[str],
        is_private: bool = False,
    ) -> tuple[Post, User]:
        author = await self._users.get_by_id(actor.id)
        if author is None or author.deleted_at is not None:
            raise UserUnavailableError("account is not available")
        _ensure_active(author)

        normalized_urls = [url.strip() for url in image_urls]
        if not normalized_urls or len(normalized_urls) > 10:
            raise ValueError("a post must contain between 1 and 10 images")
        if any(not url for url in normalized_urls):
            raise ValueError("image URLs must not be empty")

        now = datetime.now(UTC)
        post = Post(
            id=new_uuid7(),
            user_id=author.id,
            caption=caption.strip() if caption and caption.strip() else None,
            images=tuple(
                PostImage(position=index, url=url)
                for index, url in enumerate(normalized_urls)
            ),
            is_private=is_private,
            created_at=now,
            updated_at=now,
        )
        return await self._posts.add(post), author

    async def get_post(self, *, post_id: UUID, viewer: User) -> tuple[Post, User]:
        post = await self._posts.get_by_id(post_id)
        if post is None:
            raise PostNotFoundError("post was not found")

        author = await self._active_author(post.user_id)
        await self._assert_author_visible(viewer.id, author)
        if not self._is_visible_to(post, viewer_id=viewer.id):
            raise PostNotFoundError("post was not found")
        return post, author

    async def list_posts_by_author(
        self,
        *,
        username: str,
        viewer: User,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Post], User, str | None]:
        author = await self._users.get_by_username(username.strip().lower())
        if (
            author is None
            or author.deleted_at is not None
            or author.status != UserStatus.ACTIVE
        ):
            raise PostNotFoundError("author was not found")

        await self._assert_author_visible(viewer.id, author)
        decoded_cursor = _decode_post_cursor(cursor)
        before_created_at, before_id = (
            decoded_cursor if decoded_cursor is not None else (None, None)
        )
        posts = await self._posts.list_by_author(
            author.id,
            viewer_id=viewer.id,
            before_created_at=before_created_at,
            before_id=before_id,
            limit=limit,
        )
        has_more = len(posts) > limit
        page = posts[:limit]
        next_cursor = _encode_post_cursor(page[-1]) if has_more and page else None
        return page, author, next_cursor

    async def delete_post(self, *, post_id: UUID, actor: User) -> None:
        author_actor = await self._users.get_by_id(actor.id)
        if author_actor is None or author_actor.deleted_at is not None:
            raise UserUnavailableError("account is not available")
        _ensure_active(author_actor)
        post = await self._posts.get_by_id(post_id)
        if post is None:
            raise PostNotFoundError("post was not found")
        if post.user_id != actor.id:
            raise PostForbiddenError("you may only delete your own posts")
        await self._posts.soft_delete(post_id, deleted_at=datetime.now(UTC))
