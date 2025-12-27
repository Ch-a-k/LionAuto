from tortoise import fields, models

class CarModel(models.Model):
    id = fields.IntField(pk=True)
    brand = fields.ForeignKeyField("models.Brand", related_name="car_models")
    model_name = fields.CharField(max_length=100)
    year = fields.SmallIntField()
    length_mm = fields.IntField(null=True)
    width_mm = fields.IntField(null=True)
    height_mm = fields.IntField(null=True)
    wheelbase_mm = fields.IntField(null=True)

    class Meta:
        table = "models"
        unique_together = ("brand", "model_name", "year")