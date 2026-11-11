from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


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
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
