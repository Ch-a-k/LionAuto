import uuid
from tortoise import fields, models

from app.enums.two_factor_method import TwoFactorMethod


class TwoFactorBackupCode(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.ForeignKeyField("models.User", related_name="backup_codes")
    code = fields.CharField(max_length=45, unique=True)
    is_used = fields.BooleanField(default=False)
    used_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "two_factor_backup_codes"


class TwoFactorAttempt(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.ForeignKeyField("models.User", related_name="two_fa_attempts")
    method = fields.CharEnumField(TwoFactorMethod)
    success = fields.BooleanField()
    ip_address = fields.CharField(max_length=45, null=True)
    user_agent = fields.CharField(max_length=512, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "two_factor_attempts"
        ordering = ["-created_at"]
