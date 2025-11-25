from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from uuid import UUID

from app.models.user import User
from app.api.dependencies import get_current_active_user
from app.schemas.profile import UserProfileUpdate, UserProfileResponse, AvatarUploadResponse

router = APIRouter()


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's profile"""
    return current_user


@router.put("/me", response_model=UserProfileResponse)
async def update_my_profile(
    profile_update: UserProfileUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """Update current user's profile"""
    update_data = profile_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await current_user.save()
    return current_user


@router.post("/me/avatar", response_model=AvatarUploadResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Upload user avatar"""
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )

    # Validate file size (max 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must not exceed 5MB"
        )

    # TODO: Upload to S3 or storage service
    # For now, we'll just create a placeholder URL
    # In production, use the existing S3 service in the codebase

    # Example:
    # from app.services.storage import upload_file_to_s3
    # avatar_url = await upload_file_to_s3(content, file.filename, "avatars")

    avatar_url = f"https://storage.example.com/avatars/{current_user.id}/{file.filename}"

    current_user.avatar_url = avatar_url
    await current_user.save()

    return AvatarUploadResponse(avatar_url=avatar_url)


@router.delete("/me/avatar")
async def delete_avatar(
    current_user: User = Depends(get_current_active_user)
):
    """Delete user avatar"""
    # TODO: Delete from S3 or storage service
    current_user.avatar_url = None
    await current_user.save()

    return {"message": "Avatar deleted successfully"}


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Get user profile by ID (for admins or public profiles)"""
    user = await User.get_or_none(id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check permissions (admins can view any profile)
    is_admin = await current_user.has_role("admin")
    if not is_admin and user.id != current_user.id:
        # Return limited public profile
        # For now, just check if they can view the profile
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this profile"
        )

    return user
