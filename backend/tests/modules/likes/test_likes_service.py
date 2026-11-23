from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.modules.likes.models import LikeStatus
from app.modules.likes.service import LikeService
from app.modules.posts.service import PostNotFoundError
from app.modules.users.models import User, UserStatus


def run(coroutine: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coroutine)


def make_user() -> User:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return User(
        id=uuid4(),
        username="alice",
        email="alice@example.com",
        bio=None,
        avatar_key=None,
        is_private=False,
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


class FakePostService:
    def __init__(self, post_id: UUID) -> None:
        self.post_id = post_id
        self.visible = True

    async def get_post(self, *, post_id: UUID, viewer: User):
        if post_id != self.post_id or not self.visible:
            raise PostNotFoundError("post was not found")
        return object(), object()


class FakeLikeRepository:
    def __init__(self) -> None:
        self.likes: set[tuple[UUID, UUID]] = set()

    async def add(self, user_id: UUID, post_id: UUID, created_at: datetime) -> bool:
        key = (user_id, post_id)
        if key in self.likes:
            return False
        self.likes.add(key)
        return True

    async def remove(self, user_id: UUID, post_id: UUID) -> bool:
        key = (user_id, post_id)
        if key not in self.likes:
            return False
        self.likes.remove(key)
        return True

    async def get_status(self, user_id: UUID, post_id: UUID) -> tuple[bool, int]:
        return (
            (user_id, post_id) in self.likes,
            sum(liked_post_id == post_id for _, liked_post_id in self.likes),
        )


def make_service() -> tuple[LikeService, FakeLikeRepository, FakePostService, User, UUID]:
    actor = make_user()
    post_id = uuid4()
    repository = FakeLikeRepository()
    posts = FakePostService(post_id)
    return LikeService(repository, posts), repository, posts, actor, post_id


def test_like_is_idempotent_and_returns_current_count() -> None:
    service, repository, _, actor, post_id = make_service()

    first = run(service.like(post_id=post_id, actor=actor))
    second = run(service.like(post_id=post_id, actor=actor))

    assert first == LikeStatus(post_id=post_id, liked=True, like_count=1)
    assert second == first
    assert len(repository.likes) == 1


def test_unlike_is_idempotent_and_does_not_go_below_zero() -> None:
    service, _, _, actor, post_id = make_service()

    first = run(service.unlike(post_id=post_id, actor=actor))
    run(service.like(post_id=post_id, actor=actor))
    second = run(service.unlike(post_id=post_id, actor=actor))
    third = run(service.unlike(post_id=post_id, actor=actor))

    assert first.like_count == 0
    assert second == LikeStatus(post_id=post_id, liked=False, like_count=0)
    assert third == second


def test_like_is_rejected_when_post_is_not_visible() -> None:
    service, repository, posts, actor, post_id = make_service()
    posts.visible = False

    with pytest.raises(PostNotFoundError):
        run(service.like(post_id=post_id, actor=actor))

    assert repository.likes == set()


def test_status_requires_post_visibility() -> None:
    service, _, posts, actor, post_id = make_service()
    posts.visible = False

    with pytest.raises(PostNotFoundError):
        run(service.get_status(post_id=post_id, actor=actor))
