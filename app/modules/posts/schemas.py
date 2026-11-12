from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PostImageInput(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class PostCreateRequest(BaseModel):
    caption: str | None = Field(default=None, max_length=2200)
    post_img_url: list[PostImageInput] = Field(min_length=1, max_length=10)
    is_private: bool = False


class PostImageResponse(BaseModel):
    position: int
    url: str


class PostResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    user_avatar: str | None
    caption: str | None
    post_img_url: list[PostImageResponse]
    created_at: datetime
    is_private: bool
    is_deleted: bool


class PostListResponse(BaseModel):
    posts: list[PostResponse]
    limit: int
    next_cursor: str | None
