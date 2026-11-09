"""HTTP schemas for the users module.

Field visibility rules
----------------------
OwnProfileResponse   – fields visible only to the authenticated owner:
                        id, username, email, bio, avatar_key, is_private,
                        status, created_at, updated_at
PublicProfileResponse – fields visible to any authenticated caller:
                        username, bio, avatar_key, is_private, created_at.
                        email, status, updated_at are intentionally omitted.

Internal / authentication fields (password_hash, deleted_at, JWT claims)
are never present in any response schema.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class OwnProfileResponse(BaseModel):
    """Fields returned when the authenticated user fetches their own profile."""

    id: UUID
    username: str
    email: str
    bio: str | None
    avatar_key: str | None
    is_private: bool
    status: str
    created_at: datetime
    updated_at: datetime


class PublicProfileResponse(BaseModel):
    """Fields returned when any caller fetches another user's public profile."""

    username: str
    bio: str | None
    avatar_key: str | None
    is_private: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class UpdateProfileRequest(BaseModel):
    """Editable profile fields.  Every field is optional (PATCH semantics).

    Non-editable via this endpoint: id, email, status, created_at, deleted_at.
    Email changes require a separate verified-email flow (not yet implemented).
    """

    bio: str | None = Field(default=None, max_length=500)
    is_private: bool | None = None
    # avatar_key is set by the media upload flow, not directly by the client,
    # so it is intentionally absent here.
