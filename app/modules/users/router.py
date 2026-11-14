from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.auth.dependencies import DatabaseSession, get_current_user
from app.modules.users.models import User
from app.modules.users.repository import SqlAlchemyUserRepository
from app.modules.users.schemas import (
    OwnProfileResponse,
    PublicProfileResponse,
    UpdateProfileRequest,
)
from app.modules.users.service import (
    ForbiddenError,
    UserNotFoundError,
    UserPendingDeletionError,
    UserService,
    UserSuspendedError,
)

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Injectable service factory — override in tests via dependency_overrides
# ---------------------------------------------------------------------------


def get_user_service(
    session: DatabaseSession,
) -> UserService:
    return UserService(SqlAlchemyUserRepository(session))


def _own_profile_response(user: User) -> OwnProfileResponse:
    return OwnProfileResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        bio=user.bio,
        avatar_key=user.avatar_key,
        is_private=user.is_private,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _public_profile_response(user: User) -> PublicProfileResponse:
    return PublicProfileResponse(
        username=user.username,
        bio=user.bio,
        avatar_key=user.avatar_key,
        is_private=user.is_private,
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=OwnProfileResponse,
    summary="Get own profile",
    description=(
        "Returns all profile fields for the currently authenticated user, "
        "including private fields such as email and status."
    ),
)
async def get_own_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> OwnProfileResponse:
    return _own_profile_response(current_user)


@router.patch(
    "/me",
    response_model=OwnProfileResponse,
    summary="Update own profile",
    description=(
        "Update editable profile fields (bio, is_private). "
        "Uses PATCH semantics: only provided fields are changed. "
        "Non-editable fields: id, email, username, status, created_at."
    ),
)
async def update_own_profile(
    payload: UpdateProfileRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> OwnProfileResponse:
    kwargs: dict[str, object] = {}
    # Only pass fields that were explicitly set in the request body.
    if payload.bio is not None:
        kwargs["bio"] = payload.bio
    if payload.is_private is not None:
        kwargs["is_private"] = payload.is_private

    try:
        updated = await service.update_profile(
            actor=current_user,
            target_user_id=current_user.id,
            **kwargs,
        )
    except UserSuspendedError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended.",
        ) from error
    except UserPendingDeletionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is scheduled for deletion.",
        ) from error
    except ForbiddenError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(error)
        ) from error
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    return _own_profile_response(updated)


@router.get(
    "/{username}",
    response_model=PublicProfileResponse,
    summary="Get public profile",
    description=(
        "Returns the public-facing profile for the given username. "
        "Private fields (email, status, updated_at) are never included. "
        "Suspended or pending-deletion accounts appear as 404 to prevent "
        "leaking account existence."
    ),
)
async def get_public_profile(
    username: str,
    service: Annotated[UserService, Depends(get_user_service)],
) -> PublicProfileResponse:
    try:
        user = await service.get_public_profile(username)
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    return _public_profile_response(user)
