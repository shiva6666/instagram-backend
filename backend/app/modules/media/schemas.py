from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MediaUploadRequest(BaseModel):
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0, le=10_485_760)


class MediaUploadResponse(BaseModel):
    media_id: UUID
    upload_url: str
    method: str = "PUT"
    content_type: str
    expires_at: datetime


class MediaStatusResponse(BaseModel):
    media_id: UUID
    status: str
    content_type: str | None
    size_bytes: int | None
    width: int | None
    height: int | None
    failure_reason: str | None
    cleanup_requested_at: datetime | None
