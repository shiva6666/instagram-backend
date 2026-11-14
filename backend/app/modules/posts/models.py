from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class PostVisibility:
    """Public-facing visibility states for a post before media processing."""

    PUBLIC = "public"
    PRIVATE = "private"
    ALL = frozenset({PUBLIC, PRIVATE})


class PostLifecycle:
    """Lifecycle states for a post while it is created, published, or removed."""

    DRAFT = "draft"
    PUBLISHED = "published"
    SOFT_DELETED = "soft_deleted"
    ARCHIVED = "archived"
    ALL = frozenset({DRAFT, PUBLISHED, SOFT_DELETED, ARCHIVED})


@dataclass(frozen=True, slots=True)
class PostImage:
    position: int
    url: str


@dataclass(frozen=True, slots=True)
class Post:
    id: UUID
    user_id: UUID
    caption: str | None
    images: tuple[PostImage, ...]
    is_private: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    @property
    def visibility(self) -> str:
        return PostVisibility.PRIVATE if self.is_private else PostVisibility.PUBLIC

    @property
    def lifecycle(self) -> str:
        if self.deleted_at is not None:
            return PostLifecycle.SOFT_DELETED
        return PostLifecycle.PUBLISHED

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
