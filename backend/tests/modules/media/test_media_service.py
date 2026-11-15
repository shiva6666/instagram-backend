from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.modules.media.models import Media, MediaStatus
from app.modules.media.processing import ProcessedImage
from app.modules.media.service import (
    MediaUrlResolver,
    MediaConflictError,
    MediaForbiddenError,
    MediaService,
)
from app.modules.media.storage.interfaces import StoredObject
from app.modules.posts.models import PostImage


def run(coroutine: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coroutine)


class FakeMediaRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Media] = {}
        self.attached: set[UUID] = set()

    async def add(self, media: Media) -> Media:
        self.items[media.id] = media
        return media

    async def get_by_id(self, media_id: UUID) -> Media | None:
        return self.items.get(media_id)

    async def get_by_id_for_update(self, media_id: UUID) -> Media | None:
        return self.items.get(media_id)

    async def get_by_ids(self, media_ids: list[UUID]) -> list[Media]:
        return [self.items[item] for item in media_ids if item in self.items]

    async def get_by_ids_for_update(self, media_ids: list[UUID]) -> list[Media]:
        return await self.get_by_ids(media_ids)

    async def get_attached_ids(self, media_ids: list[UUID]) -> set[UUID]:
        return self.attached.intersection(media_ids)

    async def save(self, media: Media) -> Media:
        self.items[media.id] = media
        return media


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.ensure_called = False

    async def ensure_bucket(self) -> None:
        self.ensure_called = True

    def presign_put_url(self, object_key: str, *, expires_in: int) -> str:
        return f"https://storage.example/{object_key}?put={expires_in}"

    def presign_get_url(self, object_key: str, *, expires_in: int) -> str:
        return f"https://storage.example/{object_key}?get={expires_in}"

    async def head_object(self, object_key: str) -> StoredObject:
        return StoredObject(size_bytes=4, content_type="image/png")

    async def get_object(self, object_key: str, *, max_bytes: int) -> bytes:
        return b"data"

    async def put_object(
        self, object_key: str, data: bytes, *, content_type: str
    ) -> None:
        self.objects[object_key] = data

    async def delete_object(self, object_key: str) -> None:
        self.objects.pop(object_key, None)


class FakeProcessor:
    async def process(
        self, image_bytes: bytes, *, declared_content_type: str
    ) -> ProcessedImage:
        return ProcessedImage(
            content_type=declared_content_type,
            width=640,
            height=480,
            display_bytes=b"display",
            thumbnail_bytes=b"thumbnail",
        )


def service_for() -> tuple[MediaService, FakeMediaRepository, FakeStorage]:
    repository = FakeMediaRepository()
    storage = FakeStorage()
    return MediaService(repository, storage, FakeProcessor()), repository, storage


def test_create_upload_creates_pending_asset_and_presigned_url() -> None:
    service, repository, storage = service_for()
    owner_id = uuid4()

    ticket = run(
        service.create_upload(
            owner_id=owner_id,
            content_type="image/png",
            size_bytes=4,
        )
    )

    media = repository.items[ticket.media_id]
    assert storage.ensure_called
    assert media.owner_id == owner_id
    assert media.status == MediaStatus.PENDING
    assert media.expected_size_bytes == 4
    assert media.object_key is not None
    assert ticket.upload_url.startswith("https://storage.example/")
    assert ticket.content_type == "image/png"


def test_create_upload_rejects_unsupported_content_type() -> None:
    service, _repository, _storage = service_for()

    with pytest.raises(ValueError, match="JPEG, PNG, and WebP"):
        run(
            service.create_upload(
                owner_id=uuid4(),
                content_type="image/svg+xml",
                size_bytes=4,
            )
        )


def test_complete_upload_processes_variants_and_is_idempotent() -> None:
    service, repository, storage = service_for()
    owner_id = uuid4()
    now = datetime.now(UTC)
    media = Media(
        id=uuid4(),
        owner_id=owner_id,
        object_key="original/test/source",
        url=None,
        content_type="image/png",
        size_bytes=None,
        status=MediaStatus.PENDING,
        width=None,
        height=None,
        created_at=now,
        updated_at=now,
        expected_size_bytes=4,
        upload_expires_at=now + timedelta(minutes=10),
    )
    repository.items[media.id] = media

    completed = run(service.complete_upload(owner_id=owner_id, media_id=media.id))
    again = run(service.complete_upload(owner_id=owner_id, media_id=media.id))

    assert completed.status == MediaStatus.READY
    assert completed.width == 640
    assert completed.height == 480
    assert completed.display_object_key is not None
    assert completed.thumbnail_object_key is not None
    assert len(storage.objects) == 2
    assert again == completed


def test_complete_upload_rejects_another_users_media() -> None:
    service, repository, _storage = service_for()
    now = datetime.now(UTC)
    media = Media(
        id=uuid4(),
        owner_id=uuid4(),
        object_key="original/test/source",
        url=None,
        content_type="image/png",
        size_bytes=None,
        status=MediaStatus.PENDING,
        width=None,
        height=None,
        created_at=now,
        updated_at=now,
        expected_size_bytes=4,
        upload_expires_at=now + timedelta(minutes=10),
    )
    repository.items[media.id] = media

    with pytest.raises(MediaForbiddenError):
        run(service.complete_upload(owner_id=uuid4(), media_id=media.id))


def test_discard_rejects_already_attached_media() -> None:
    service, repository, _storage = service_for()
    now = datetime.now(UTC)
    media = Media(
        id=uuid4(),
        owner_id=uuid4(),
        object_key="original/test/source",
        url=None,
        content_type="image/png",
        size_bytes=None,
        status=MediaStatus.READY,
        width=10,
        height=10,
        created_at=now,
        updated_at=now,
        expected_size_bytes=4,
    )
    repository.items[media.id] = media
    repository.attached.add(media.id)

    with pytest.raises(MediaConflictError, match="attached"):
        run(service.discard(owner_id=media.owner_id, media_id=media.id))


def test_discard_marks_unattached_media_for_cleanup() -> None:
    service, repository, _storage = service_for()
    now = datetime.now(UTC)
    media = Media(
        id=uuid4(),
        owner_id=uuid4(),
        object_key="original/test/source",
        url=None,
        content_type="image/png",
        size_bytes=None,
        status=MediaStatus.PENDING,
        width=None,
        height=None,
        created_at=now,
        updated_at=now,
    )
    repository.items[media.id] = media

    discarded = run(service.discard(owner_id=media.owner_id, media_id=media.id))

    assert discarded.cleanup_requested_at is not None
    assert repository.items[media.id].cleanup_requested_at is not None


def test_complete_upload_marks_size_mismatch_failed() -> None:
    service, repository, _storage = service_for()
    owner_id = uuid4()
    now = datetime.now(UTC)
    media = Media(
        id=uuid4(),
        owner_id=owner_id,
        object_key="original/test/source",
        url=None,
        content_type="image/png",
        size_bytes=None,
        status=MediaStatus.PENDING,
        width=None,
        height=None,
        created_at=now,
        updated_at=now,
        expected_size_bytes=5,
        upload_expires_at=now + timedelta(minutes=10),
    )
    repository.items[media.id] = media

    failed = run(service.complete_upload(owner_id=owner_id, media_id=media.id))

    assert failed.status == MediaStatus.FAILED
    assert failed.failure_reason == "uploaded size does not match the declared size"


def test_media_url_resolver_signs_private_processed_media() -> None:
    owner_id = uuid4()
    media = make_media_for_resolver(owner_id)
    repository = FakeMediaRepository()
    repository.items[media.id] = media
    storage = FakeStorage()
    resolver = MediaUrlResolver(repository, storage)

    images = run(
        resolver.resolve(
            (
                PostImage(position=0, url=None, media_id=media.id),
                PostImage(position=1, url="https://legacy.example/image.jpg"),
            )
        )
    )

    assert images[0].url.startswith("https://storage.example/")
    assert images[1].url == "https://legacy.example/image.jpg"


def make_media_for_resolver(owner_id: UUID) -> Media:
    now = datetime.now(UTC)
    return Media(
        id=uuid4(),
        owner_id=owner_id,
        object_key="original/test/source",
        url=None,
        content_type="image/png",
        size_bytes=100,
        status=MediaStatus.READY,
        width=640,
        height=480,
        created_at=now,
        updated_at=now,
        expected_size_bytes=100,
        display_object_key="processed/test/display.webp",
        thumbnail_object_key="processed/test/thumbnail.webp",
    )


def test_complete_upload_allows_finalization_after_upload_url_expiry() -> None:
    service, repository, _storage = service_for()
    owner_id = uuid4()
    now = datetime.now(UTC)
    media = Media(
        id=uuid4(),
        owner_id=owner_id,
        object_key="original/test/source",
        url=None,
        content_type="image/png",
        size_bytes=None,
        status=MediaStatus.PENDING,
        width=None,
        height=None,
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
        expected_size_bytes=4,
        upload_expires_at=now - timedelta(minutes=1),
    )
    repository.items[media.id] = media

    completed = run(service.complete_upload(owner_id=owner_id, media_id=media.id))

    assert completed.status == MediaStatus.READY
