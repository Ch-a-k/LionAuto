from tortoise import fields, models

class Brand(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)  # Оригинальное название

    class Meta:
        table = "brands"