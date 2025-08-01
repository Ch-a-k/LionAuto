from tortoise import Tortoise
from loguru import logger
from app.core.config import settings

class DatabaseManager:
    @staticmethod
    async def init():
        """Initialize database with schema and default data"""
        await Tortoise.init(
            db_url=settings.database_url,
            modules={"models": ["app.models"]}
        )
        await Tortoise.generate_schemas(safe=True)
        logger.info("✅ Database schema initialized")

    @staticmethod
    async def close():
        """Close database connections"""
        await Tortoise.close_connections()
        logger.info("🛑 Database connections closed")