import pytest
from httpx import AsyncClient

from app.models.user import User
from app.models.notification import Notification, NotificationType, NotificationChannel


@pytest.mark.asyncio
async def test_get_notifications(client: AsyncClient, test_user: User, user_token: str):
    """Test getting user notifications"""
    # Create test notifications
    await Notification.create(
        user=test_user,
        notification_type=NotificationType.info,
        title="Test Notification 1",
        message="Test message 1",
        channel=NotificationChannel.in_app
    )
    await Notification.create(
        user=test_user,
        notification_type=NotificationType.success,
        title="Test Notification 2",
        message="Test message 2",
        channel=NotificationChannel.in_app,
        is_read=True
    )

    response = await client.get(
        "/notifications/",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["unread_count"] == 1
    assert len(data["notifications"]) == 2


@pytest.mark.asyncio
async def test_get_unread_notifications(client: AsyncClient, test_user: User, user_token: str):
    """Test getting only unread notifications"""
    await Notification.create(
        user=test_user,
        notification_type=NotificationType.info,
        title="Unread",
        message="Unread message",
        is_read=False
    )
    await Notification.create(
        user=test_user,
        notification_type=NotificationType.info,
        title="Read",
        message="Read message",
        is_read=True
    )

    response = await client.get(
        "/notifications/?unread_only=true",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["notifications"][0]["title"] == "Unread"
    assert data["notifications"][0]["is_read"] is False


@pytest.mark.asyncio
async def test_mark_notification_as_read(client: AsyncClient, test_user: User, user_token: str):
    """Test marking a notification as read"""
    notification = await Notification.create(
        user=test_user,
        notification_type=NotificationType.info,
        title="Test",
        message="Test message",
        is_read=False
    )

    response = await client.put(
        f"/notifications/{notification.id}/read",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200

    # Verify in database
    await notification.refresh_from_db()
    assert notification.is_read is True
    assert notification.read_at is not None


@pytest.mark.asyncio
async def test_mark_all_as_read(client: AsyncClient, test_user: User, user_token: str):
    """Test marking all notifications as read"""
    # Create multiple unread notifications
    for i in range(3):
        await Notification.create(
            user=test_user,
            notification_type=NotificationType.info,
            title=f"Test {i}",
            message=f"Message {i}",
            is_read=False
        )

    response = await client.put(
        "/notifications/read-all",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200

    # Verify all marked as read
    unread_count = await Notification.filter(user=test_user, is_read=False).count()
    assert unread_count == 0


@pytest.mark.asyncio
async def test_delete_notification(client: AsyncClient, test_user: User, user_token: str):
    """Test deleting a notification"""
    notification = await Notification.create(
        user=test_user,
        notification_type=NotificationType.info,
        title="Test",
        message="Test message"
    )

    response = await client.delete(
        f"/notifications/{notification.id}",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200

    # Verify deleted
    exists = await Notification.exists(id=notification.id)
    assert exists is False


@pytest.mark.asyncio
async def test_get_notification_preferences(client: AsyncClient, test_user: User, user_token: str):
    """Test getting notification preferences"""
    response = await client.get(
        "/notifications/preferences",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    # Default preferences
    assert data["email_enabled"] is True
    assert data["in_app_enabled"] is True
    assert data["bid_notifications"] is True


@pytest.mark.asyncio
async def test_update_notification_preferences(client: AsyncClient, test_user: User, user_token: str):
    """Test updating notification preferences"""
    update_data = {
        "email_enabled": False,
        "telegram_enabled": True,
        "bid_notifications": False
    }

    response = await client.put(
        "/notifications/preferences",
        headers={"Authorization": f"Bearer {user_token}"},
        json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email_enabled"] is False
    assert data["telegram_enabled"] is True
    assert data["bid_notifications"] is False
