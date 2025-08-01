from tortoise import models, fields
from uuid import uuid4
from datetime import datetime, timedelta

class RefreshToken(models.Model):
    id = fields.UUIDField(pk=True, default=uuid4)
    user = fields.ForeignKeyField("models.User", related_name="refresh_tokens", on_delete=fields.CASCADE)
    token = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField()

    class Meta:
        table = "refresh_tokens"

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
