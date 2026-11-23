from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class LikeStatus:
    post_id: UUID
    liked: bool
    like_count: int
