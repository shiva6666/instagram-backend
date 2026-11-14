from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.modules.auth.dependencies import DatabaseSession, get_current_user
from app.modules.posts.models import Post
from app.modules.posts.repository import SqlAlchemyPostRepository
from app.modules.posts.schemas import (
    PostCreateRequest,
    PostImageResponse,
    PostListResponse,
    PostResponse,
)
from app.modules.posts.service import (
    InvalidPostCursorError,
    PostForbiddenError,
    PostNotFoundError,
    PostService,
    UserUnavailableError,
)
from app.modules.users.models import User
from app.modules.users.repository import SqlAlchemyUserRepository

router = APIRouter(prefix="/posts", tags=["posts"])


def get_post_service(
    session: DatabaseSession,
) -> PostService:
    return PostService(
        SqlAlchemyPostRepository(session),
        SqlAlchemyUserRepository(session),
    )


def _response(post: Post, author: User) -> PostResponse:
    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        username=author.username,
        user_avatar=author.avatar_key,
        caption=post.caption,
        post_img_url=[
            PostImageResponse(position=image.position, url=image.url)
            for image in post.images
        ],
        created_at=post.created_at,
        is_private=post.is_private,
        is_deleted=post.is_deleted,
    )


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a post",
)
async def create_post(
    payload: PostCreateRequest,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[PostService, Depends(get_post_service)],
) -> PostResponse:
    try:
        post, author = await service.create_post(
            actor=actor,
            caption=payload.caption,
            image_urls=[image.url for image in payload.post_img_url],
            is_private=payload.is_private,
        )
    except UserUnavailableError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _response(post, author)


@router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="Get a post",
)
async def get_post(
    post_id: UUID,
    viewer: Annotated[User, Depends(get_current_user)],
    service: Annotated[PostService, Depends(get_post_service)],
) -> PostResponse:
    try:
        post, author = await service.get_post(post_id=post_id, viewer=viewer)
    except PostNotFoundError as error:
        raise HTTPException(status_code=404, detail="Post was not found") from error
    return _response(post, author)


@router.get(
    "/users/{username}",
    response_model=PostListResponse,
    summary="List posts by author",
)
async def list_posts_by_author(
    username: str,
    viewer: Annotated[User, Depends(get_current_user)],
    service: Annotated[PostService, Depends(get_post_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> PostListResponse:
    try:
        posts, _author, next_cursor = await service.list_posts_by_author(
            username=username,
            viewer=viewer,
            cursor=cursor,
            limit=limit,
        )
    except PostNotFoundError as error:
        raise HTTPException(status_code=404, detail="Author was not found") from error
    except InvalidPostCursorError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return PostListResponse(
        posts=[_response(post, _author) for post in posts],
        limit=limit,
        next_cursor=next_cursor,
    )


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a post",
)
async def delete_post(
    post_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[PostService, Depends(get_post_service)],
) -> Response:
    try:
        await service.delete_post(post_id=post_id, actor=actor)
    except PostNotFoundError as error:
        raise HTTPException(status_code=404, detail="Post was not found") from error
    except PostForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except UserUnavailableError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
