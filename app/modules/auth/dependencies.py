from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.tokens import InvalidAccessTokenError, decode_access_token
from app.modules.users.models import User
from app.modules.users.repository import SqlAlchemyUserRepository

bearer_scheme = HTTPBearer()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DatabaseSession = Annotated[
    AsyncSession, Depends(get_db_session, scope="function")
]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    session: DatabaseSession,
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except (InvalidAccessTokenError, RuntimeError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    user = await SqlAlchemyUserRepository(session).get_by_id(user_id)
    if user is None or user.status != "active" or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is unavailable",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
