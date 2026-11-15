from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.modules.auth.dependencies import get_current_user
from app.modules.media.dependencies import get_media_service
from app.modules.media.models import Media
from app.modules.media.schemas import (
    MediaStatusResponse,
    MediaUploadRequest,
    MediaUploadResponse,
)
from app.modules.media.service import (
    MediaConflictError,
    MediaForbiddenError,
    MediaNotFoundError,
    MediaService,
    MediaUploadMissingError,
)
from app.modules.users.models import User

router = APIRouter(prefix="/media", tags=["media"])


def _status_response(media: Media) -> MediaStatusResponse:
    return MediaStatusResponse(
        media_id=media.id,
        status=media.status,
        content_type=media.content_type,
        size_bytes=media.size_bytes,
        width=media.width,
        height=media.height,
        failure_reason=media.failure_reason,
        cleanup_requested_at=media.cleanup_requested_at,
    )


@router.post(
    "/upload-url",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a presigned image upload",
)
async def create_upload(
    payload: MediaUploadRequest,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[MediaService, Depends(get_media_service)],
) -> MediaUploadResponse:
    try:
        ticket = await service.create_upload(
            owner_id=actor.id,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return MediaUploadResponse(
        media_id=ticket.media_id,
        upload_url=ticket.upload_url,
        content_type=ticket.content_type,
        expires_at=ticket.expires_at,
    )


@router.post(
    "/{media_id}/complete",
    response_model=MediaStatusResponse,
    summary="Verify and process an uploaded image",
)
async def complete_upload(
    media_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[MediaService, Depends(get_media_service)],
) -> MediaStatusResponse:
    try:
        media = await service.complete_upload(owner_id=actor.id, media_id=media_id)
    except MediaNotFoundError as error:
        raise HTTPException(status_code=404, detail="Media was not found") from error
    except MediaForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except MediaUploadMissingError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except MediaConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _status_response(media)


@router.get(
    "/{media_id}",
    response_model=MediaStatusResponse,
    summary="Get the current media processing state",
)
async def get_media(
    media_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[MediaService, Depends(get_media_service)],
) -> MediaStatusResponse:
    try:
        media = await service.get_status(owner_id=actor.id, media_id=media_id)
    except MediaNotFoundError as error:
        raise HTTPException(status_code=404, detail="Media was not found") from error
    except MediaForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    return _status_response(media)


@router.delete(
    "/{media_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Schedule unattached media for cleanup",
)
async def discard_media(
    media_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[MediaService, Depends(get_media_service)],
) -> Response:
    try:
        await service.discard(owner_id=actor.id, media_id=media_id)
    except MediaNotFoundError as error:
        raise HTTPException(status_code=404, detail="Media was not found") from error
    except MediaForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except MediaConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return Response(status_code=status.HTTP_202_ACCEPTED)
