from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class UserStatus:
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_DELETION = "pending_deletion"

    ALL = frozenset({ACTIVE, SUSPENDED, PENDING_DELETION})


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    username: str
    email: str
    bio: str | None
    avatar_key: str | None
    is_private: bool
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
