from tortoise import fields, models
from datetime import datetime
import os

def generate_image_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    safe_name = f"{timestamp}{ext}"
    return f"car_models/{instance.model_id}/{safe_name}"

class CarModelImage(models.Model):
    id = fields.IntField(pk=True)
    model = fields.ForeignKeyField("models.CarModel", related_name="images", on_delete=fields.CASCADE)
    image_path = fields.CharField(max_length=255)  
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "car_model_images"