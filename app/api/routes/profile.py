from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File

from app.models.user import User
from app.api.dependencies import get_current_active_user
from app.schemas.profile import UserProfileUpdate, UserProfileResponse, AvatarUploadResponse
from app.services.store.s3contabo import s3_service

from uuid import UUID, uuid4
from pathlib import Path
from io import BytesIO

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
    """Upload user avatar to Contabo S3"""
    # 1) Проверка типа
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )

    # 2) Проверка размера (max 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must not exceed 5MB"
        )

    # 3) Генерация безопасного ключа для S3
    #    avatars/<user_id>/<uuid4>.<ext>
    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    key = f"avatars/{current_user.id}/{uuid4().hex}{ext}"

    # 4) Загрузка в S3 (public-read)
    fileobj = BytesIO(content)
    await s3_service.upload_fileobj(
        fileobj=fileobj,
        key=key,
        content_type=file.content_type,
        public_read=True,
    )

    # 5) Публичный URL для фронта
    avatar_url = s3_service.build_public_url(key)

    # 6) Сохраняем в БД
    current_user.avatar_url = avatar_url
    await current_user.save()

    return AvatarUploadResponse(avatar_url=avatar_url)


@router.delete("/me/avatar")
async def delete_avatar(
    current_user: User = Depends(get_current_active_user)
):
    """Delete user avatar from S3 and clear field"""
    old_url = current_user.avatar_url

    if old_url:
        # Пробуем вытащить key из публичного URL
        base = s3_service.public_base_url.rstrip("/")  # type: ignore[attr-defined]
        # public_base_url задаётся в S3Service.__init__
        if old_url.startswith(base + "/"):
            key = old_url[len(base) + 1 :]
            try:
                s3_service.delete_object(key)
            except Exception:
                # Лог уже внутри S3Service, тут просто продолжаем,
                # чтобы не ронять запрос, если объект уже удалён и т.п.
                pass

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
