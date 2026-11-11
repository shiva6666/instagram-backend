from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.modules.posts.models import Post, PostImage
from app.modules.posts.service import (
    PostForbiddenError,
    PostNotFoundError,
    PostService,
    UserUnavailableError,
)
from app.modules.users.models import User, UserStatus


def run(coroutine: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coroutine)


def make_user(
    *,
    user_id: UUID | None = None,
    username: str = "alice",
    is_private: bool = False,
    status: str = UserStatus.ACTIVE,
    deleted_at: datetime | None = None,
) -> User:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return User(
        id=user_id or uuid4(),
        username=username,
        email=f"{username}@example.com",
        bio=None,
        avatar_key=None,
        is_private=is_private,
        status=status,
        created_at=now,
        updated_at=now,
        deleted_at=deleted_at,
    )


class FakePostRepository:
    def __init__(self) -> None:
        self.posts: dict[UUID, Post] = {}
        self.follows: set[tuple[UUID, UUID]] = set()
        self.blocks: set[tuple[UUID, UUID]] = set()

    async def add(self, post: Post) -> Post:
        self.posts[post.id] = post
        return post

    async def get_by_id(self, post_id: UUID) -> Post | None:
        post = self.posts.get(post_id)
        return post if post is not None and post.deleted_at is None else None

    async def list_by_author(
        self, author_id: UUID, *, offset: int, limit: int
    ) -> list[Post]:
        items = sorted(
            (
                post
                for post in self.posts.values()
                if post.user_id == author_id and post.deleted_at is None
            ),
            key=lambda post: (post.created_at, post.id),
            reverse=True,
        )
        return items[offset : offset + limit + 1]

    async def soft_delete(self, post_id: UUID, *, deleted_at: datetime) -> None:
        post = self.posts[post_id]
        self.posts[post_id] = Post(
            id=post.id,
            user_id=post.user_id,
            caption=post.caption,
            images=post.images,
            is_private=post.is_private,
            created_at=post.created_at,
            updated_at=deleted_at,
            deleted_at=deleted_at,
        )

    async def is_following(self, follower_id: UUID, followee_id: UUID) -> bool:
        return (follower_id, followee_id) in self.follows

    async def is_blocked_between(self, first_user_id: UUID, second_user_id: UUID) -> bool:
        return (
            (first_user_id, second_user_id) in self.blocks
            or (second_user_id, first_user_id) in self.blocks
        )


class FakeUserRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = {user.id: user for user in users}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_username(self, username: str) -> User | None:
        return next(
            (user for user in self.users.values() if user.username == username),
            None,
        )


def service_for(
    users: list[User],
) -> tuple[PostService, FakePostRepository]:
    posts = FakePostRepository()
    service = PostService(posts, FakeUserRepository(users))
    return service, posts


def test_create_post_uses_authenticated_author_and_orders_images() -> None:
    alice = make_user()
    service, _ = service_for([alice])

    post, author = run(
        service.create_post(
            actor=alice,
            caption="  hello world  ",
            image_urls=[" https://cdn.example/one.jpg ", "https://cdn.example/two.jpg"],
        )
    )

    assert post.user_id == alice.id
    assert author.id == alice.id
    assert post.caption == "hello world"
    assert post.images == (
        PostImage(position=0, url="https://cdn.example/one.jpg"),
        PostImage(position=1, url="https://cdn.example/two.jpg"),
    )


def test_create_post_rejects_inactive_author() -> None:
    suspended = make_user(status=UserStatus.SUSPENDED)
    service, _ = service_for([suspended])

    with pytest.raises(UserUnavailableError):
        run(
            service.create_post(
                actor=suspended,
                caption=None,
                image_urls=["https://cdn.example/image.jpg"],
            )
        )


def test_get_post_hides_private_post_from_non_owner() -> None:
    alice = make_user()
    bob = make_user(username="bob")
    service, _repository = service_for([alice, bob])
    post, _ = run(
        service.create_post(
            actor=alice,
            caption=None,
            image_urls=["https://cdn.example/image.jpg"],
            is_private=True,
        )
    )

    with pytest.raises(PostNotFoundError):
        run(service.get_post(post_id=post.id, viewer=bob))


def test_private_author_requires_accepted_follow() -> None:
    alice = make_user(is_private=True)
    bob = make_user(username="bob")
    service, repository = service_for([alice, bob])
    post, _ = run(
        service.create_post(
            actor=alice,
            caption=None,
            image_urls=["https://cdn.example/image.jpg"],
        )
    )

    with pytest.raises(PostNotFoundError):
        run(service.get_post(post_id=post.id, viewer=bob))

    repository.follows.add((bob.id, alice.id))
    result, _ = run(service.get_post(post_id=post.id, viewer=bob))
    assert result.id == post.id


def test_block_in_either_direction_hides_post() -> None:
    alice = make_user()
    bob = make_user(username="bob")
    service, repository = service_for([alice, bob])
    post, _ = run(
        service.create_post(
            actor=alice,
            caption=None,
            image_urls=["https://cdn.example/image.jpg"],
        )
    )
    repository.blocks.add((alice.id, bob.id))

    with pytest.raises(PostNotFoundError):
        run(service.get_post(post_id=post.id, viewer=bob))


def test_delete_post_is_owner_only_and_soft_deletes() -> None:
    alice = make_user()
    bob = make_user(username="bob")
    service, repository = service_for([alice, bob])
    post, _ = run(
        service.create_post(
            actor=alice,
            caption=None,
            image_urls=["https://cdn.example/image.jpg"],
        )
    )

    with pytest.raises(PostForbiddenError):
        run(service.delete_post(post_id=post.id, actor=bob))

    run(service.delete_post(post_id=post.id, actor=alice))
    assert repository.posts[post.id].deleted_at is not None
    with pytest.raises(PostNotFoundError):
        run(service.get_post(post_id=post.id, viewer=alice))


def test_list_posts_by_author_returns_next_offset_when_more_exist() -> None:
    alice = make_user()
    service, _ = service_for([alice])
    for index in range(3):
        run(
            service.create_post(
                actor=alice,
                caption=str(index),
                image_urls=[f"https://cdn.example/{index}.jpg"],
            )
        )

    posts, author, next_offset = run(
        service.list_posts_by_author(
            username="alice",
            viewer=alice,
            offset=0,
            limit=2,
        )
    )

    assert len(posts) == 2
    assert author.id == alice.id
    assert next_offset == 2
