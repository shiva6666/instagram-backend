from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.core.config import settings
from app.core.ids import new_uuid7
from app.modules.media.models import Media, MediaStatus
from app.modules.media.processing import ImageProcessor, InvalidImageError
from app.modules.media.repository import MediaRepository
from app.modules.media.storage.interfaces import (
    ObjectNotFoundError,
    ObjectStorage,
)


ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


class MediaNotFoundError(LookupError):
    pass


class MediaForbiddenError(PermissionError):
    pass


class MediaConflictError(RuntimeError):
    pass


class MediaUploadMissingError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class UploadTicket:
    media_id: UUID
    upload_url: str
    expires_at: datetime
    content_type: str


class ImageReference(Protocol):
    position: int
    url: str | None
    media_id: UUID | None


class ImageReference(Protocol):
    position: int
    url: str | None
    media_id: UUID | None


@dataclass(frozen=True, slots=True)
class ResolvedImage:
    position: int
    url: str


class MediaService:
    def __init__(
        self,
        repository: MediaRepository,
        storage: ObjectStorage,
        processor: ImageProcessor,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._processor = processor

    async def create_upload(
        self, *, owner_id: UUID, content_type: str, size_bytes: int
    ) -> UploadTicket:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError("only JPEG, PNG, and WebP images are accepted")
        if size_bytes <= 0 or size_bytes > settings.media_max_upload_bytes:
            raise ValueError("image size is outside the allowed range")

        await self._storage.ensure_bucket()
        now = datetime.now(UTC)
        media_id = new_uuid7()
        object_key = f"original/{owner_id}/{media_id}/source"
        expires_at = now + timedelta(seconds=settings.media_upload_ttl_seconds)
        media = Media(
            id=media_id,
            owner_id=owner_id,
            object_key=object_key,
            url=None,
            content_type=content_type,
            size_bytes=None,
            status=MediaStatus.PENDING,
            width=None,
            height=None,
            created_at=now,
            updated_at=now,
            expected_size_bytes=size_bytes,
            upload_expires_at=expires_at,
        )
        await self._repository.add(media)
        upload_url = self._storage.presign_put_url(
            object_key, expires_in=settings.media_upload_ttl_seconds
        )
        return UploadTicket(
            media_id=media_id,
            upload_url=upload_url,
            expires_at=expires_at,
            content_type=content_type,
        )

    async def complete_upload(self, *, owner_id: UUID, media_id: UUID) -> Media:
        media = await self._repository.get_by_id_for_update(media_id)
        if media is None:
            raise MediaNotFoundError("media was not found")
        if media.owner_id != owner_id:
            raise MediaForbiddenError("media does not belong to this user")
        if (
            media.status == MediaStatus.DELETING
            or media.cleanup_requested_at is not None
        ):
            raise MediaConflictError("media is scheduled for cleanup")
        if media.status == MediaStatus.READY:
            return media
        if media.status not in {MediaStatus.PENDING, MediaStatus.FAILED}:
            raise MediaConflictError("media cannot be completed in its current state")
        if media.object_key is None or media.expected_size_bytes is None:
            raise MediaConflictError("media upload metadata is incomplete")

        now = datetime.now(UTC)
        try:
            stored = await self._storage.head_object(media.object_key)
        except ObjectNotFoundError as error:
            if media.upload_expires_at is not None and now > media.upload_expires_at:
                failed = replace(
                    media,
                    status=MediaStatus.FAILED,
                    failure_reason="upload URL expired before an object was uploaded",
                    updated_at=now,
                    cleanup_requested_at=now,
                )
                return await self._repository.save(failed)
            raise MediaUploadMissingError(
                "uploaded object was not found; upload it before completing"
            ) from error

        if stored.size_bytes != media.expected_size_bytes:
            failed = replace(
                media,
                status=MediaStatus.FAILED,
                failure_reason="uploaded size does not match the declared size",
                updated_at=now,
            )
            return await self._repository.save(failed)
        if stored.size_bytes > settings.media_max_upload_bytes:
            failed = replace(
                media,
                status=MediaStatus.FAILED,
                failure_reason="uploaded object exceeds the size limit",
                updated_at=now,
            )
            return await self._repository.save(failed)
        if stored.content_type and stored.content_type != media.content_type:
            failed = replace(
                media,
                status=MediaStatus.FAILED,
                failure_reason="uploaded content type does not match the declaration",
                updated_at=now,
            )
            return await self._repository.save(failed)

        processing = replace(
            media, status=MediaStatus.PROCESSING, failure_reason=None, updated_at=now
        )
        await self._repository.save(processing)
        source = await self._storage.get_object(
            media.object_key, max_bytes=settings.media_max_upload_bytes
        )
        try:
            processed = await self._processor.process(
                source, declared_content_type=media.content_type or ""
            )
        except InvalidImageError as error:
            failed = replace(
                processing,
                status=MediaStatus.FAILED,
                failure_reason=str(error)[:240],
                updated_at=datetime.now(UTC),
            )
            return await self._repository.save(failed)

        display_key = f"processed/{owner_id}/{media_id}/display.webp"
        thumbnail_key = f"processed/{owner_id}/{media_id}/thumbnail.webp"
        await self._storage.put_object(
            display_key, processed.display_bytes, content_type="image/webp"
        )
        await self._storage.put_object(
            thumbnail_key, processed.thumbnail_bytes, content_type="image/webp"
        )
        ready = replace(
            processing,
            status=MediaStatus.READY,
            size_bytes=stored.size_bytes,
            width=processed.width,
            height=processed.height,
            display_object_key=display_key,
            thumbnail_object_key=thumbnail_key,
            failure_reason=None,
            updated_at=datetime.now(UTC),
        )
        return await self._repository.save(ready)

    async def get_status(self, *, owner_id: UUID, media_id: UUID) -> Media:
        media = await self._repository.get_by_id(media_id)
        if media is None:
            raise MediaNotFoundError("media was not found")
        if media.owner_id != owner_id:
            raise MediaForbiddenError("media does not belong to this user")
        return media

    async def discard(self, *, owner_id: UUID, media_id: UUID) -> Media:
        media = await self._repository.get_by_id_for_update(media_id)
        if media is None:
            raise MediaNotFoundError("media was not found")
        if media.owner_id != owner_id:
            raise MediaForbiddenError("media does not belong to this user")
        if media.status == MediaStatus.DELETING:
            return media
        attached = await self._repository.get_attached_ids([media_id])
        if attached:
            raise MediaConflictError("attached media cannot be discarded")
        if media.cleanup_requested_at is not None:
            return media
        return await self._repository.save(
            replace(
                media,
                cleanup_requested_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )


class MediaUrlResolver:
    """Creates short-lived read URLs only after post/feed visibility is checked."""

    def __init__(self, repository: MediaRepository, storage: ObjectStorage) -> None:
        self._repository = repository
        self._storage = storage

    async def resolve(self, images: tuple[ImageReference, ...]) -> list[ResolvedImage]:
        media_ids = [
            image.media_id
            for image in images
            if image.media_id is not None and image.url is None
        ]
        media_by_id = {
            media.id: media
            for media in await self._repository.get_by_ids(media_ids)
        }
        resolved: list[ResolvedImage] = []
        for image in images:
            position = image.position
            url = image.url
            media_id = image.media_id
            if url:
                resolved.append(ResolvedImage(position=position, url=url))
                continue
            media = media_by_id.get(media_id)
            if (
                media is None
                or media.status != MediaStatus.READY
                or media.display_object_key is None
            ):
                raise RuntimeError("post references media that is not ready")
            resolved.append(
                ResolvedImage(
                    position=position,
                    url=self._storage.presign_get_url(
                        media.display_object_key,
                        expires_in=settings.media_download_ttl_seconds,
                    ),
                )
            )
        return resolved
