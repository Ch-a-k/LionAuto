from tortoise import fields, models

class ModelAttribute(models.Model):
    model = fields.ForeignKeyField(
        "models.CarModel", 
        related_name="attributes",
        on_delete=fields.CASCADE
        )
    attribute_type = fields.ForeignKeyField("models.AttributeType")
    language_code = fields.CharField(max_length=2)
    value = fields.TextField()

    class Meta:
        table = "model_attributes"
        unique_together = ("model", "attribute_type", "language_code")


class ModelColor(models.Model):
    model = fields.ForeignKeyField(
        "models.CarModel", 
        related_name="colors",
        on_delete=fields.CASCADE
        )
    color_type = fields.ForeignKeyField("models.ColorType")
    language_code = fields.CharField(max_length=2)
    color_name = fields.CharField(max_length=100)

    class Meta:
        table = "model_colors"
        unique_together = ("model", "color_type", "language_code", "color_name")