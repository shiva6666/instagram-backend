from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from app.modules.auth.dependencies import DatabaseSession
from app.modules.media.processing import ImageMagickProcessor
from app.modules.media.repository import SqlAlchemyMediaRepository
from app.modules.media.service import MediaService, MediaUrlResolver
from app.modules.media.storage.s3 import S3CompatibleStorage


def get_object_storage() -> S3CompatibleStorage:
    return S3CompatibleStorage.from_settings()


def get_media_service(
    session: DatabaseSession,
    storage: Annotated[S3CompatibleStorage, Depends(get_object_storage)],
) -> MediaService:
    return MediaService(
        SqlAlchemyMediaRepository(session),
        storage,
        ImageMagickProcessor(),
    )


def get_media_url_resolver(
    session: DatabaseSession,
    storage: Annotated[S3CompatibleStorage, Depends(get_object_storage)],
) -> MediaUrlResolver:
    return MediaUrlResolver(SqlAlchemyMediaRepository(session), storage)
