from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.modules.auth.dependencies import DatabaseSession, get_current_user
from app.modules.likes.repository import SqlAlchemyLikeRepository
from app.modules.likes.schemas import LikeStatusResponse
from app.modules.likes.service import LikeService
from app.modules.posts.repository import SqlAlchemyPostRepository
from app.modules.posts.service import PostNotFoundError, PostService
from app.modules.users.models import User
from app.modules.users.repository import SqlAlchemyUserRepository

router = APIRouter(prefix="/posts", tags=["likes"])


def get_like_service(session: DatabaseSession) -> LikeService:
    posts = PostService(
        SqlAlchemyPostRepository(session),
        SqlAlchemyUserRepository(session),
    )
    return LikeService(SqlAlchemyLikeRepository(session), posts)


def _response(result) -> LikeStatusResponse:
    return LikeStatusResponse(
        post_id=result.post_id,
        liked=result.liked,
        like_count=result.like_count,
    )


@router.get(
    "/{post_id}/like",
    response_model=LikeStatusResponse,
    summary="Get the authenticated user's like state for a post",
)
async def get_like_status(
    post_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[LikeService, Depends(get_like_service)],
) -> LikeStatusResponse:
    try:
        result = await service.get_status(post_id=post_id, actor=actor)
    except PostNotFoundError as error:
        raise HTTPException(status_code=404, detail="Post was not found") from error
    return _response(result)


@router.post(
    "/{post_id}/like",
    response_model=LikeStatusResponse,
    summary="Like a post",
)
async def like_post(
    post_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[LikeService, Depends(get_like_service)],
) -> LikeStatusResponse:
    try:
        result = await service.like(post_id=post_id, actor=actor)
    except PostNotFoundError as error:
        raise HTTPException(status_code=404, detail="Post was not found") from error
    return _response(result)


@router.delete(
    "/{post_id}/like",
    response_model=LikeStatusResponse,
    summary="Unlike a post",
)
async def unlike_post(
    post_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[LikeService, Depends(get_like_service)],
) -> LikeStatusResponse:
    try:
        result = await service.unlike(post_id=post_id, actor=actor)
    except PostNotFoundError as error:
        raise HTTPException(status_code=404, detail="Post was not found") from error
    return _response(result)
