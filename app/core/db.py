from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine: AsyncEngine | None = (
    create_async_engine(settings.database_url, pool_pre_ping=True)
    if settings.database_url
    else None
)

session_factory = (
    async_sessionmaker(engine, expire_on_commit=False) if engine is not None else None
)


async def check_database() -> bool:
    if engine is None:
        return False

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    if session_factory is None:
        raise RuntimeError("DATABASE_URL must be configured to use database sessions")

    async with session_factory() as session:
        yield session


async def close_database() -> None:
    if engine is not None:
        await engine.dispose()
