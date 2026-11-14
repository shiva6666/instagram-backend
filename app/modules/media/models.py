from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class MediaStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ALL = frozenset({PENDING, PROCESSING, READY, FAILED})


@dataclass(frozen=True, slots=True)
class Media:
    id: UUID
    owner_id: UUID
    object_key: str | None
    url: str
    content_type: str | None
    size_bytes: int | None
    status: str
    width: int | None
    height: int | None
    created_at: datetime
    updated_at: datetime
