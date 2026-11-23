from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class LikeStatusResponse(BaseModel):
    post_id: UUID
    liked: bool
    like_count: int = Field(ge=0)
