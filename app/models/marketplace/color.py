from tortoise import fields, models

class ColorType(models.Model):
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=50, unique=True)

    class Meta:
        table = "color_types"