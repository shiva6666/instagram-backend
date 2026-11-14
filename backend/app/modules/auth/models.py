from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthIdentity:
    id: UUID
    user_id: UUID
    provider: str
    provider_subject: str
    password_hash: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshToken:
    id: UUID
    user_id: UUID
    family_id: UUID
    token_hash: str
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None
    replaced_by_token_id: UUID | None = None
