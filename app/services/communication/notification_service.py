from uuid import UUID
from typing import Optional
from datetime import datetime

from app.models.user import User
from app.models.notification import (
    Notification,
    NotificationType,
    NotificationChannel,
    NotificationPreference
)
from app.models.bid import Bid
from app.models.deposit import Deposit


class NotificationService:
    @staticmethod
    async def create_notification(
        user: User,
        notification_type: NotificationType,
        title: str,
        message: str,
        channel: NotificationChannel = NotificationChannel.in_app,
        related_bid: Optional[Bid] = None,
        related_deposit: Optional[Deposit] = None,
        action_url: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Notification:
        """Create a new notification"""
        notification = await Notification.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            channel=channel,
            related_bid=related_bid,
            related_deposit=related_deposit,
            action_url=action_url,
            metadata=metadata
        )

        # TODO: Send to external channels (email, SMS, etc.) based on preferences
        await NotificationService._send_to_channels(user, notification)

        return notification

    @staticmethod
    async def _send_to_channels(user: User, notification: Notification):
        """Send notification to configured channels"""
        try:
            preferences = await NotificationPreference.get_or_none(user=user)

            if not preferences:
                # Create default preferences
                preferences = await NotificationPreference.create(user=user)

            # Check preferences and send to appropriate channels
            # TODO: Implement actual email/SMS/Telegram/WhatsApp sending

            if preferences.email_enabled and user.email:
                # await EmailService.send_notification_email(user.email, notification)
                pass

            if preferences.telegram_enabled and user.tg_username:
                # await TelegramService.send_notification(user.tg_username, notification)
                pass

            if preferences.whatsapp_enabled and user.whatsapp_phone:
                # await WhatsAppService.send_notification(user.whatsapp_phone, notification)
                pass

        except Exception as e:
            # Log error but don't fail notification creation
            print(f"Error sending notification to channels: {e}")

    @staticmethod
    async def get_user_notifications(
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False
    ) -> tuple[list[Notification], int, int]:
        """Get user notifications with pagination"""
        query = Notification.filter(user_id=user_id)

        if unread_only:
            query = query.filter(is_read=False)

        total = await query.count()
        unread_count = await Notification.filter(user_id=user_id, is_read=False).count()

        notifications = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)

        return notifications, total, unread_count

    @staticmethod
    async def mark_as_read(notification_id: UUID, user_id: UUID) -> Notification:
        """Mark a notification as read"""
        notification = await Notification.get(id=notification_id, user_id=user_id)

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            await notification.save()

        return notification

    @staticmethod
    async def mark_all_as_read(user_id: UUID) -> int:
        """Mark all notifications as read for a user"""
        count = await Notification.filter(user_id=user_id, is_read=False).update(
            is_read=True,
            read_at=datetime.utcnow()
        )
        return count

    @staticmethod
    async def delete_notification(notification_id: UUID, user_id: UUID):
        """Delete a notification"""
        await Notification.filter(id=notification_id, user_id=user_id).delete()

    @staticmethod
    async def get_or_create_preferences(user: User) -> NotificationPreference:
        """Get or create notification preferences for a user"""
        preferences = await NotificationPreference.get_or_none(user=user)

        if not preferences:
            preferences = await NotificationPreference.create(user=user)

        return preferences

    @staticmethod
    async def update_preferences(user: User, **kwargs) -> NotificationPreference:
        """Update notification preferences"""
        preferences = await NotificationService.get_or_create_preferences(user)

        for key, value in kwargs.items():
            if value is not None and hasattr(preferences, key):
                setattr(preferences, key, value)

        await preferences.save()
        return preferences
