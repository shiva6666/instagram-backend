import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.core.cache import check_redis
from app.core.db import check_database

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", tags=["health"])
async def readiness_check() -> JSONResponse:
    try:
        database_ready = await check_database()
    except SQLAlchemyError:
        logger.warning("database_readiness_check_failed", exc_info=True)
        database_ready = False

    try:
        redis_ready = await check_redis()
    except RedisError:
        logger.warning("redis_readiness_check_failed", exc_info=True)
        redis_ready = False

    checks = {
        "postgres": "ok" if database_ready else "unavailable",
        "redis": "ok" if redis_ready else "unavailable",
    }
    is_ready = database_ready and redis_ready

    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
        },
    )
