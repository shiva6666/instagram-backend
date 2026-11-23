from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Like:
    user_id: UUID
    post_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LikeStatus:
    post_id: UUID
    liked: bool
    like_count: int
