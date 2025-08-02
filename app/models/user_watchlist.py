from tortoise import fields
from tortoise.models import Model
from uuid import uuid4, UUID

class UserWatchlist(Model):
    id = fields.UUIDField(pk=True, default=uuid4)
    user_id = fields.UUIDField()  # FK на User (можно использовать fields.ForeignKeyField если есть модель User)
    lot_id = fields.UUIDField()   # FK на Lot

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_watchlist"
        unique_together = ("user_id", "lot_id")  # Чтобы запретить дублирование
