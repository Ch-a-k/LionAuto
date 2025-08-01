from tortoise import fields
from tortoise.models import Model
from uuid import uuid4
from app.enums.bid_status import BidStatus

class Bid(Model):
    id = fields.UUIDField(pk=True, default=uuid4)

    user = fields.ForeignKeyField("models.User", related_name="bids", on_delete=fields.CASCADE)
    lot = fields.ForeignKeyField("models.Lot", related_name="bids", on_delete=fields.CASCADE)

    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    status = fields.CharEnumField(BidStatus, default=BidStatus.pending)

    bidding_data = fields.JSONField(default=dict)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "bids"

    async def save(self, *args, **kwargs):
        if self.amount <= 0:
            raise ValueError("Amount must be greater than 0")
        await super().save(*args, **kwargs)

