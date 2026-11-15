from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class MediaStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"
    ALL = frozenset({PENDING, PROCESSING, READY, FAILED, DELETING})


@dataclass(frozen=True, slots=True)
class Media:
    id: UUID
    owner_id: UUID
    object_key: str | None
    url: str | None
    content_type: str | None
    size_bytes: int | None
    status: str
    width: int | None
    height: int | None
    created_at: datetime
    updated_at: datetime
    expected_size_bytes: int | None = None
    upload_expires_at: datetime | None = None
    display_object_key: str | None = None
    thumbnail_object_key: str | None = None
    cleanup_requested_at: datetime | None = None
    failure_reason: str | None = None
