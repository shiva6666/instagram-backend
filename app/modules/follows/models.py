from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.users.models import User


class FollowStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    ALL = frozenset({PENDING, ACCEPTED})


@dataclass(frozen=True, slots=True)
class FollowRelationship:
    follower_id: UUID
    following_id: UUID
    status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class FollowedUser:
    user: User
    followed_at: datetime
