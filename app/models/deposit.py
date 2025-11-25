import uuid
from tortoise import fields, models

from app.enums.deposit_status import DepositStatus
from app.enums.payment_method import PaymentMethod


class Deposit(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.ForeignKeyField("models.User", related_name="deposits")
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    currency = fields.CharField(max_length=3, default="USD")
    status = fields.CharEnumField(DepositStatus, default=DepositStatus.pending)
    payment_method = fields.CharEnumField(PaymentMethod)

    # Payment details
    transaction_id = fields.CharField(max_length=255, null=True, unique=True)
    payment_reference = fields.CharField(max_length=255, null=True)
    payment_details = fields.JSONField(null=True)

    # Additional info
    description = fields.TextField(null=True)
    admin_notes = fields.TextField(null=True)

    # Timestamps
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    completed_at = fields.DatetimeField(null=True)

    class Meta:
        table = "deposits"

    def __str__(self):
        return f"Deposit {self.id} - {self.amount} {self.currency} ({self.status})"
