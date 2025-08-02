import json
from app.models.user_watchlist import UserWatchlist
from app.services.kafka.producer import kafka_producer

TOPIC = "auction.lot.watch_updates"

async def notify_watchlist_users(lot_id, changes: dict):
    # Получаем всех пользователей, отслеживающих лот
    entries = await UserWatchlist.filter(lot_id=lot_id).all()
    user_ids = [str(entry.user_id) for entry in entries]

    if not user_ids:
        return

    message = {
        "lot_id": str(lot_id),
        "changes": changes,
        "user_ids": user_ids
    }

    kafka_producer.produce(
        topic=TOPIC,
        value=json.dumps(message),
        key=str(lot_id)
    )
    kafka_producer.flush()
