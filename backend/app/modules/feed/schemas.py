from __future__ import annotations

from pydantic import BaseModel

from app.modules.posts.schemas import PostResponse


class FeedResponse(BaseModel):
    posts: list[PostResponse]
    limit: int
    next_cursor: str | None
