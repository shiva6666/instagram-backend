from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.follows.models import (
    FollowRelationship,
    FollowStatus,
    FollowedUser,
)
from app.modules.follows.repository import FollowRepository
from app.modules.users.models import User, UserStatus
from app.modules.users.repository import UserRepository


class FollowTargetNotFoundError(LookupError):
    """The target account does not exist or is not publicly available."""


class FollowSelfError(ValueError):
    """A user cannot follow themselves."""


class FollowRequestNotFoundError(LookupError):
    """No pending follow request exists for the requested transition."""


class FollowForbiddenError(PermissionError):
    """The viewer is not allowed to see or change the relationship."""


class InvalidFollowCursorError(ValueError):
    """The supplied follow-list cursor is malformed."""


@dataclass(frozen=True, slots=True)
class FollowPage:
    users: tuple[FollowedUser, ...]
    next_cursor: str | None


def _encode_cursor(item: FollowedUser, *, followers: bool) -> str:
    user_id = item.user.id
    payload = {
        "created_at": item.followed_at.isoformat(),
        "user_id": str(user_id),
        "direction": "followers" if followers else "following",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(
    cursor: str | None, *, followers: bool
) -> tuple[datetime, UUID] | None:
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if payload["direction"] != ("followers" if followers else "following"):
            raise ValueError("cursor direction does not match")
        created_at = datetime.fromisoformat(payload["created_at"])
        user_id = UUID(payload["user_id"])
        if created_at.tzinfo is None:
            raise ValueError("cursor timestamp must include timezone")
        return created_at, user_id
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise InvalidFollowCursorError("invalid follow-list cursor") from error


class FollowService:
    def __init__(
        self, follows: FollowRepository, users: UserRepository
    ) -> None:
        self._follows = follows
        self._users = users

    async def _active_user(self, username: str) -> User:
        user = await self._users.get_by_username(username.strip().lower())
        if (
            user is None
            or user.deleted_at is not None
            or user.status != UserStatus.ACTIVE
        ):
            raise FollowTargetNotFoundError("user was not found")
        return user

    async def follow(self, *, actor: User, username: str) -> FollowRelationship:
        target = await self._active_user(username)
        if actor.id == target.id:
            raise FollowSelfError("you cannot follow yourself")
        if await self._follows.is_blocked_between(actor.id, target.id):
            raise FollowTargetNotFoundError("user was not found")
        existing = await self._follows.get_relationship(actor.id, target.id)
        if existing is not None:
            return existing

        status = (
            FollowStatus.PENDING if target.is_private else FollowStatus.ACCEPTED
        )
        return await self._follows.add_relationship(
            actor.id, target.id, status, datetime.now(UTC)
        )

    async def unfollow(self, *, actor: User, username: str) -> None:
        target = await self._active_user(username)
        if actor.id == target.id:
            raise FollowSelfError("you cannot unfollow yourself")
        await self._follows.remove_relationship(actor.id, target.id)

    async def accept_request(
        self, *, actor: User, follower_username: str
    ) -> FollowRelationship:
        follower = await self._active_user(follower_username)
        relationship = await self._follows.accept_request(follower.id, actor.id)
        if relationship is None or relationship.status != FollowStatus.ACCEPTED:
            raise FollowRequestNotFoundError("pending follow request was not found")
        return relationship

    async def reject_request(
        self, *, actor: User, follower_username: str
    ) -> None:
        follower = await self._active_user(follower_username)
        removed = await self._follows.remove_relationship(
            follower.id, actor.id, pending_only=True
        )
        if not removed:
            raise FollowRequestNotFoundError("pending follow request was not found")

    async def relationship(
        self, *, viewer: User, username: str
    ) -> FollowRelationship | None:
        target = await self._active_user(username)
        return await self._follows.get_relationship(viewer.id, target.id)

    async def _assert_graph_visible(self, *, viewer: User, target: User) -> None:
        if viewer.id == target.id or not target.is_private:
            return
        relationship = await self._follows.get_relationship(viewer.id, target.id)
        if relationship is None or relationship.status != FollowStatus.ACCEPTED:
            raise FollowTargetNotFoundError("user was not found")

    async def _list(
        self,
        *,
        viewer: User,
        username: str,
        cursor: str | None,
        limit: int,
        followers: bool,
    ) -> FollowPage:
        target = await self._active_user(username)
        await self._assert_graph_visible(viewer=viewer, target=target)
        decoded = _decode_cursor(cursor, followers=followers)
        if followers:
            items = await self._follows.list_followers(
                target.id, cursor=decoded, limit=limit
            )
        else:
            items = await self._follows.list_following(
                target.id, cursor=decoded, limit=limit
            )
        has_more = len(items) > limit
        page = tuple(items[:limit])
        next_cursor = (
            _encode_cursor(page[-1], followers=followers)
            if has_more and page
            else None
        )
        return FollowPage(users=page, next_cursor=next_cursor)

    async def list_followers(
        self, *, viewer: User, username: str, cursor: str | None, limit: int
    ) -> FollowPage:
        return await self._list(
            viewer=viewer,
            username=username,
            cursor=cursor,
            limit=limit,
            followers=True,
        )

    async def list_following(
        self, *, viewer: User, username: str, cursor: str | None, limit: int
    ) -> FollowPage:
        return await self._list(
            viewer=viewer,
            username=username,
            cursor=cursor,
            limit=limit,
            followers=False,
        )

    async def counts(self, *, viewer: User, username: str) -> tuple[int, int]:
        target = await self._active_user(username)
        await self._assert_graph_visible(viewer=viewer, target=target)
        return (
            await self._follows.count_followers(target.id),
            await self._follows.count_following(target.id),
        )
