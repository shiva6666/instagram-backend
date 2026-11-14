from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.posts.models import Post


@dataclass(frozen=True, slots=True)
class FeedAuthor:
    id: UUID
    username: str
    avatar_key: str | None


@dataclass(frozen=True, slots=True)
class FeedItem:
    post: Post
    author: FeedAuthor
