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

        # Создаем GIN индекс для полнотекстового поиска на lot
        conn = Tortoise.get_connection("default")
        await conn.execute_query("""
            CREATE INDEX IF NOT EXISTS lot_search_idx
            ON lot USING GIN (to_tsvector('simple', coalesce(location, '') || ' ' || coalesce(state, '')));
        """)
        logger.info("✅ GIN index lot_search_idx created or already exists")

    @staticmethod
    async def close():
        """Close database connections"""
        await Tortoise.close_connections()
        logger.info("🛑 Database connections closed")
