# app/main.py (фрагменты)
import asyncio
import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
from app.core.config import settings
from app.api.routes import (
    user_router, documents_router, customers_router,
    role_router, user_auction_router, lots_router,
    watchlist_router, copart_route, iaai_route, audit_router,
    bot_session_router, debug_router
)
from app.core.database import DatabaseManager
from app.services.init_service import InitService
from app.api.dependencies import get_current_user
from app.services.kafka.producer import KafkaProducer
import clamd
from app.services.kafka.admin import KafkaAdmin

from app.services.copart_controller import CopartController

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting up {settings.app_name} v{settings.version}...")

    # --- ClamAV, DB, Kafka и т.п. как было ---
    try:
        cd = clamd.ClamdNetworkSocket(host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT, timeout=30)
        if not cd.ping():
            logger.warning("ClamAV responded but ping failed")
        else:
            logger.info("ClamAV connection verified successfully")
    except clamd.ConnectionError as e:
        logger.error(f"ClamAV connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error verifying ClamAV: {str(e)}")

    db = DatabaseManager()
    await db.init()
    await InitService.init_roles_permissions()
    await InitService.create_default_user()

    app.state.kafka_producer = KafkaProducer()
    admin = KafkaAdmin()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, admin.create_topics)

    # --- CopartController: создаём и, при желании, автозапускаем ---
    # app.state.copart_controller = CopartController(
    #     username=settings.COPART_USER,
    #     password=settings.COPART_PASS,
    #     headless=settings.HEADLESS,
    #     session_db="sessions.db",
    # )
    # if settings.COPART_AUTOSTART:
    #     try:
    #         await app.state.copart_controller.start()
    #     except Exception as e:
    #         logger.exception(f"Copart autostart failed: {e}")

    try:
        yield
    finally:
        logger.info("Shutting down...")
        # try:
        #     # Корректно останавливаем бота
        #     if getattr(app.state, "copart_controller", None):
        #         await app.state.copart_controller.stop()
        # except Exception:
        #     logger.exception("Error stopping Copart controller")
        app.state.kafka_producer.flush()
        await db.close()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
    debug=settings.debug
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

app.include_router(
    documents_router,
    prefix="/kyc",
    tags=["Documents"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    customers_router,
    prefix="/kyc",
    tags=["Customers"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    role_router,
    prefix="/role",
    tags=["Role"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    user_auction_router,
    prefix="/user_auction",
    tags=["User Auctions"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    lots_router,
    prefix="/lots",
    tags=["Lots"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    watchlist_router,
    prefix="/watchlist",
    tags=["Watchlist"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    iaai_route,
    prefix="/iaai",
    tags=["IAAI"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    copart_route,
    prefix="/copart",
    tags=["Copart"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    user_router,
    prefix="/user",
    tags=["User"]
)

app.include_router(
    audit_router,
    prefix="/audit",
    tags=["Audit Logs"],
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    bot_session_router,
    dependencies=[Depends(get_current_user)]
)

app.include_router(
    debug_router,
    dependencies=[Depends(get_current_user)]
)

async def main():
    """ Main function to run FastAPI with multiple workers. """
    config = uvicorn.Config(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,   # ⚠️ Playwright плохо дружит с многими воркерами!
        reload=settings.debug
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
