# app/schemas/profile.py
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from typing import Optional


class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserProfileResponse(BaseModel):
    id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    kyc_access: bool
    created_at: datetime
    updated_at: datetime

    # для работы с ORM-объектами (Tortoise)
    model_config = ConfigDict(from_attributes=True)


class AvatarUploadResponse(BaseModel):
    avatar_url: str