from redis.asyncio import Redis
from app.core.config import settings

_redis = None

async def get_redis_client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis
