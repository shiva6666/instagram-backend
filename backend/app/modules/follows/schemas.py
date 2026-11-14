from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FollowRelationshipResponse(BaseModel):
    follower_id: UUID
    following_id: UUID
    status: str
    created_at: datetime


class FollowUserResponse(BaseModel):
    id: UUID
    username: str
    bio: str | None
    avatar_key: str | None
    is_private: bool
    created_at: datetime
    followed_at: datetime


class FollowListResponse(BaseModel):
    users: list[FollowUserResponse]
    limit: int
    next_cursor: str | None


class FollowCountsResponse(BaseModel):
    followers: int
    following: int


class FollowStatusResponse(BaseModel):
    username: str
    status: str | None
    is_following: bool
    request_pending: bool
