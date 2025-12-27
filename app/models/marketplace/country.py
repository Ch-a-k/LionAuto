from tortoise import fields, models

class Country(models.Model):
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=2, unique=True)  # ISO 3166-1 alpha-2 (например, 'CN', 'PL')
    name = fields.CharField(max_length=100, unique=True)

    class Meta:
        table = "countries"