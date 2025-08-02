from uuid import UUID
from app.core.config.redis import get_redis_client

async def invalidate_lot_cache(lot_id: UUID):
    redis = await get_redis_client()
    await redis.delete(f"lot:{lot_id}")
    
    # keys возвращает список байтов, надо декодировать к строки
    keys = await redis.keys("lots:*")
    if keys:
        # Декодируем ключи в строки
        str_keys = [k.decode() if isinstance(k, bytes) else k for k in keys]
        if str_keys:
            await redis.delete(*str_keys)
