from redis.asyncio import Redis

from app.core.config import settings

redis_client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)


async def check_redis() -> bool:
    return bool(await redis_client.ping())


async def close_redis() -> None:
    await redis_client.aclose()
