from app.core.config.celery import celery_app
from loguru import logger

@celery_app.task
def validate_auction_account(account_id: int):
    # Здесь пишем логику проверки (логин в аукцион и т.п.)
    logger.info(f"Validate auction account {account_id}")
    # Можно обновить статус в базе и т.п.
