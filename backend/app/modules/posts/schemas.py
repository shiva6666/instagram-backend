from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PostImageInput(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class PostCreateRequest(BaseModel):
    caption: str | None = Field(default=None, max_length=2200)
    post_img_url: list[PostImageInput] | None = Field(
        default=None, min_length=1, max_length=10
    )
    media_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=10)
    is_private: bool = False

    @model_validator(mode="after")
    def require_one_image_source(self) -> PostCreateRequest:
        if (self.post_img_url is None) == (self.media_ids is None):
            raise ValueError("provide either post_img_url or media_ids, but not both")
        return self


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
