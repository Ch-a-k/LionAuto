from uuid import UUID
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_serializer

from app.models.notification import NotificationType, NotificationChannel


class NotificationResponse(BaseModel):
    """Schema for notification response"""
    id: UUID
    notification_type: NotificationType
    title: str
    message: str
    channel: NotificationChannel
    is_read: bool
    read_at: Optional[datetime]
    action_url: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("id")
    def serialize_id(self, v: UUID, _info):
        return str(v)


class NotificationListResponse(BaseModel):
    """Schema for paginated notification list"""
    total: int
    unread_count: int
    page: int
    page_size: int
    notifications: list[NotificationResponse]


class NotificationPreferenceUpdate(BaseModel):
    """Schema for updating notification preferences"""
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    telegram_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    bid_notifications: Optional[bool] = None
    deposit_notifications: Optional[bool] = None
    kyc_notifications: Optional[bool] = None
    auction_reminders: Optional[bool] = None
    security_notifications: Optional[bool] = None


class NotificationPreferenceResponse(BaseModel):
    """Schema for notification preferences response"""
    email_enabled: bool
    sms_enabled: bool
    telegram_enabled: bool
    whatsapp_enabled: bool
    in_app_enabled: bool
    bid_notifications: bool
    deposit_notifications: bool
    kyc_notifications: bool
    auction_reminders: bool
    security_notifications: bool

    model_config = ConfigDict(from_attributes=True)
