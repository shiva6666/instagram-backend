from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.auth.dependencies import get_current_user, get_db_session
from app.modules.auth.repository import SqlAlchemyAuthRepository
from app.modules.auth.schemas import (
    LoginRequest, LogoutRequest, MessageResponse, RefreshRequest,
    RegisterRequest, TokenResponse, UserResponse,
)
from app.modules.auth.service import (
    AuthService, InvalidCredentialsError, InvalidRefreshTokenError,
    RefreshTokenReuseError,
)
from app.modules.users.models import User
from app.modules.users.repository import SqlAlchemyUserRepository, UserAlreadyExistsError

router = APIRouter(prefix="/auth", tags=["authentication"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id, username=user.username, email=user.email, bio=user.bio,
        is_private=user.is_private, status=user.status, created_at=user.created_at,
    )


def _token_response(user: User, access_token: str, refresh_token: str) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.auth_access_token_ttl_seconds,
        refresh_token=refresh_token,
        user=_user_response(user),
    )


def _service(session: AsyncSession) -> AuthService:
    return AuthService(SqlAlchemyAuthRepository(session), SqlAlchemyUserRepository(session))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, session: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    try:
        user, access, refresh = await _service(session).register(
            username=payload.username, email=str(payload.email), password=payload.password,
            bio=payload.bio, is_private=payload.is_private,
        )
    except UserAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _token_response(user, access, refresh)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, session: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    try:
        user, access, refresh = await _service(session).login(
            email=str(payload.email), password=payload.password
        )
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=401, detail="Email or password is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    return _token_response(user, access, refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest, session: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    try:
        user, access, refresh_token = await _service(session).refresh(payload.refresh_token)
    except RefreshTokenReuseError as error:
        # Persist family revocation before returning the security error.
        await session.commit()
        raise HTTPException(status_code=401, detail="Refresh token reuse detected") from error
    except InvalidRefreshTokenError as error:
        raise HTTPException(status_code=401, detail="Refresh token is invalid") from error
    return _token_response(user, access, refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    payload: LogoutRequest, session: AsyncSession = Depends(get_db_session)
) -> MessageResponse:
    await _service(session).logout(payload.refresh_token)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return _user_response(user)
