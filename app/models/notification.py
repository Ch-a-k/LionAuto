import uuid
from tortoise import fields, models

from app.enums.notification_type import NotificationType
from app.enums.notification_channel import NotificationChannel


class Notification(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.ForeignKeyField("models.User", related_name="notifications")

    # Notification content
    notification_type = fields.CharEnumField(NotificationType)
    title = fields.CharField(max_length=255)
    message = fields.TextField()

    # Delivery
    channel = fields.CharEnumField(NotificationChannel, default=NotificationChannel.in_app)
    is_read = fields.BooleanField(default=False)
    read_at = fields.DatetimeField(null=True)

    # Related entities
    related_bid = fields.ForeignKeyField("models.Bid", related_name="notifications", null=True)
    related_deposit = fields.ForeignKeyField("models.Deposit", related_name="notifications", null=True)

    # Additional data
    metadata = fields.JSONField(null=True)
    action_url = fields.CharField(max_length=512, null=True)

    # Timestamps
    created_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField(null=True)

    class Meta:
        table = "notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification {self.id} - {self.title}"


class NotificationPreference(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.OneToOneField("models.User", related_name="notification_preferences")

    # Channel preferences
    email_enabled = fields.BooleanField(default=True)
    sms_enabled = fields.BooleanField(default=False)
    telegram_enabled = fields.BooleanField(default=False)
    whatsapp_enabled = fields.BooleanField(default=False)
    in_app_enabled = fields.BooleanField(default=True)

    # Notification type preferences
    bid_notifications = fields.BooleanField(default=True)
    deposit_notifications = fields.BooleanField(default=True)
    kyc_notifications = fields.BooleanField(default=True)
    auction_reminders = fields.BooleanField(default=True)
    security_notifications = fields.BooleanField(default=True)

    # Timestamps
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "notification_preferences"
