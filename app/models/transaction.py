import uuid
from tortoise import fields, models

from app.enums.transaction_type import TransactionType
from app.enums.transaction_status import TransactionStatus


class Transaction(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.ForeignKeyField("models.User", related_name="transactions")

    # Transaction details
    transaction_type = fields.CharEnumField(TransactionType)
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    currency = fields.CharField(max_length=3, default="USD")
    status = fields.CharEnumField(TransactionStatus, default=TransactionStatus.pending)

    # Balance tracking
    balance_before = fields.DecimalField(max_digits=12, decimal_places=2)
    balance_after = fields.DecimalField(max_digits=12, decimal_places=2)

    # Related entities
    deposit = fields.ForeignKeyField("models.Deposit", related_name="transactions", null=True)
    bid = fields.ForeignKeyField("models.Bid", related_name="transactions", null=True)

    # Reference information
    reference_id = fields.CharField(max_length=255, null=True)
    description = fields.TextField(null=True)
    metadata = fields.JSONField(null=True)

    # Timestamps
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "transactions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transaction {self.id} - {self.transaction_type} {self.amount} {self.currency}"
