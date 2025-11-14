from aiocache import caches
from app.core.config import settings

def init_cache():
    caches.set_config({
        "default": {
            "cache": "aiocache.RedisCache",
            "endpoint": settings.redis_host,   # "redis"
            "port": int(settings.redis_port),  # 6379
            "db": 3,
            "serializer": {
                "class": "aiocache.serializers.JsonSerializer"
            },
            "plugins": []
        }
    })