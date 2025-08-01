# app/models/customer.py
from tortoise import fields, models
from app.enums.customer_status import CustomerStatus

class Customer(models.Model):
    user = fields.ForeignKeyField("models.User", related_name="customers")
    status = fields.CharEnumField(CustomerStatus, default=CustomerStatus.PENDING)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "customers"