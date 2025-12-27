from tortoise import fields, models

class AttributeType(models.Model):
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=50, unique=True)

    class Meta:
        table = "attribute_types"