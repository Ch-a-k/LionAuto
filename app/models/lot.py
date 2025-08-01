from tortoise import fields
from tortoise.models import Model
from uuid import uuid4
from app.enums.auction_type import AuctionType  # создадим enum отдельно

class Lot(Model):
    id = fields.UUIDField(pk=True, default=uuid4)

    auction_type = fields.CharEnumField(AuctionType)

    title = fields.TextField()
    description = fields.TextField(null=True)

    start_price = fields.DecimalField(max_digits=12, decimal_places=2)

    auction_data = fields.JSONField(default=dict)

    image_s3_keys = fields.JSONField(default=list)  # Tortoise не поддерживает PostgreSQL массивы, используем JSON
    document_s3_keys = fields.JSONField(default=list)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "lots"
