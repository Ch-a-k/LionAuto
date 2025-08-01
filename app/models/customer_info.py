# app/models/customer_info.py
from tortoise import fields, models

class CustomerInfo(models.Model):
    customer = fields.OneToOneField("models.Customer", related_name="info")
    first_name = fields.CharField(max_length=255)
    last_name = fields.CharField(max_length=255)
    birth_date = fields.DateField()
    country = fields.CharField(max_length=255)
    address = fields.CharField(max_length=512)
    city = fields.CharField(max_length=255)
    postal_code = fields.CharField(max_length=100)

    class Meta:
        table = "customer_infos"