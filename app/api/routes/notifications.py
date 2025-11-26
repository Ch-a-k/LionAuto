from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID

from app.models.user import User
from app.api.dependencies import get_current_active_user
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferenceUpdate,
    NotificationPreferenceResponse
)
from app.services.communication.notification_service import NotificationService

router = APIRouter()


@router.get("/", response_model=NotificationListResponse)
async def get_my_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's notifications"""
    notifications, total, unread_count = await NotificationService.get_user_notifications(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        unread_only=unread_only
    )

    return NotificationListResponse(
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
        notifications=notifications
    )


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_active_user)
):
    """Get count of unread notifications"""
    from app.models.notification import Notification

    count = await Notification.filter(user_id=current_user.id, is_read=False).count()
    return {"unread_count": count}


@router.put("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Mark a notification as read"""
    try:
        await NotificationService.mark_as_read(notification_id, current_user.id)
        return {"message": "Notification marked as read"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )


@router.put("/read-all")
async def mark_all_as_read(
    current_user: User = Depends(get_current_active_user)
):
    """Mark all notifications as read"""
    count = await NotificationService.mark_all_as_read(current_user.id)
    return {"message": f"{count} notifications marked as read"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Delete a notification"""
    try:
        await NotificationService.delete_notification(notification_id, current_user.id)
        return {"message": "Notification deleted"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )


# Notification preferences
@router.get("/preferences", response_model=NotificationPreferenceResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_active_user)
):
    """Get notification preferences"""
    preferences = await NotificationService.get_or_create_preferences(current_user)
    return preferences


@router.put("/preferences", response_model=NotificationPreferenceResponse)
async def update_notification_preferences(
    preferences_update: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """Update notification preferences"""
    update_data = preferences_update.model_dump(exclude_unset=True)
    preferences = await NotificationService.update_preferences(current_user, **update_data)
    return preferences
