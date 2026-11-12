from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies import get_current_user, get_db_session
from app.modules.follows.models import FollowRelationship
from app.modules.follows.repository import SqlAlchemyFollowRepository
from app.modules.follows.schemas import (
    FollowCountsResponse,
    FollowListResponse,
    FollowRelationshipResponse,
    FollowStatusResponse,
    FollowUserResponse,
)
from app.modules.follows.service import (
    FollowRequestNotFoundError,
    FollowSelfError,
    FollowService,
    FollowTargetNotFoundError,
    InvalidFollowCursorError,
)
from app.modules.users.models import User
from app.modules.users.repository import SqlAlchemyUserRepository

router = APIRouter(prefix="/follows", tags=["follows"])


def get_follow_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FollowService:
    return FollowService(
        SqlAlchemyFollowRepository(session),
        SqlAlchemyUserRepository(session),
    )


def _relationship_response(
    relationship: FollowRelationship,
) -> FollowRelationshipResponse:
    return FollowRelationshipResponse(
        follower_id=relationship.follower_id,
        following_id=relationship.following_id,
        status=relationship.status,
        created_at=relationship.created_at,
    )


def _list_response(page, *, limit: int) -> FollowListResponse:
    return FollowListResponse(
        users=[
            FollowUserResponse(
                id=item.user.id,
                username=item.user.username,
                bio=item.user.bio,
                avatar_key=item.user.avatar_key,
                is_private=item.user.is_private,
                created_at=item.user.created_at,
                followed_at=item.followed_at,
            )
            for item in page.users
        ],
        limit=limit,
        next_cursor=page.next_cursor,
    )


@router.post(
    "/{username}",
    response_model=FollowRelationshipResponse,
    summary="Follow a user or request to follow a private account",
)
async def follow_user(
    username: str,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[FollowService, Depends(get_follow_service)],
) -> FollowRelationshipResponse:
    try:
        relationship = await service.follow(actor=actor, username=username)
    except FollowSelfError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FollowTargetNotFoundError as error:
        raise HTTPException(status_code=404, detail="User was not found") from error
    return _relationship_response(relationship)


@router.delete(
    "/{username}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unfollow a user or cancel a follow request",
)
async def unfollow_user(
    username: str,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[FollowService, Depends(get_follow_service)],
) -> Response:
    try:
        await service.unfollow(actor=actor, username=username)
    except FollowSelfError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FollowTargetNotFoundError as error:
        raise HTTPException(status_code=404, detail="User was not found") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/requests/{username}/accept",
    response_model=FollowRelationshipResponse,
    summary="Accept a pending follow request",
)
async def accept_follow_request(
    username: str,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[FollowService, Depends(get_follow_service)],
) -> FollowRelationshipResponse:
    try:
        relationship = await service.accept_request(
            actor=actor, follower_username=username
        )
    except (FollowTargetNotFoundError, FollowRequestNotFoundError) as error:
        raise HTTPException(
            status_code=404, detail="Follow request was not found"
        ) from error
    return _relationship_response(relationship)


@router.delete(
    "/requests/{username}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reject a pending follow request",
)
async def reject_follow_request(
    username: str,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[FollowService, Depends(get_follow_service)],
) -> Response:
    try:
        await service.reject_request(actor=actor, follower_username=username)
    except (FollowTargetNotFoundError, FollowRequestNotFoundError) as error:
        raise HTTPException(
            status_code=404, detail="Follow request was not found"
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{username}/relationship",
    response_model=FollowStatusResponse,
    summary="Get the authenticated user's relationship with an account",
)
async def get_relationship(
    username: str,
    viewer: Annotated[User, Depends(get_current_user)],
    service: Annotated[FollowService, Depends(get_follow_service)],
) -> FollowStatusResponse:
    try:
        relationship = await service.relationship(viewer=viewer, username=username)
    except FollowTargetNotFoundError as error:
        raise HTTPException(status_code=404, detail="User was not found") from error
    return FollowStatusResponse(
        username=username,
        status=relationship.status if relationship else None,
        is_following=relationship is not None and relationship.status == "accepted",
        request_pending=relationship is not None and relationship.status == "pending",
    )


@router.get("/{username}/followers", response_model=FollowListResponse)
async def list_followers(
    username: str,
    viewer: Annotated[User, Depends(get_current_user)],
    service: Annotated[FollowService, Depends(get_follow_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> FollowListResponse:
    try:
        page = await service.list_followers(
            viewer=viewer, username=username, cursor=cursor, limit=limit
        )
    except FollowTargetNotFoundError as error:
        raise HTTPException(status_code=404, detail="User was not found") from error
    except InvalidFollowCursorError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _list_response(page, limit=limit)


@router.get("/{username}/following", response_model=FollowListResponse)
async def list_following(
    username: str,
    viewer: Annotated[User, Depends(get_current_user)],
    service: Annotated[FollowService, Depends(get_follow_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> FollowListResponse:
    try:
        page = await service.list_following(
            viewer=viewer, username=username, cursor=cursor, limit=limit
        )
    except FollowTargetNotFoundError as error:
        raise HTTPException(status_code=404, detail="User was not found") from error
    except InvalidFollowCursorError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    response = _list_response(page)
    response.limit = limit
    return response


@router.get("/{username}/counts", response_model=FollowCountsResponse)
async def get_follow_counts(
    username: str,
    viewer: Annotated[User, Depends(get_current_user)],
    service: Annotated[FollowService, Depends(get_follow_service)],
) -> FollowCountsResponse:
    try:
        followers, following = await service.counts(viewer=viewer, username=username)
    except FollowTargetNotFoundError as error:
        raise HTTPException(status_code=404, detail="User was not found") from error
    return FollowCountsResponse(followers=followers, following=following)
