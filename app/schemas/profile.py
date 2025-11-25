from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from decimal import Decimal


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile"""
    first_name: Optional[str] = Field(None, max_length=255)
    last_name: Optional[str] = Field(None, max_length=255)
    country: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    tg_phone: Optional[str] = Field(None, max_length=50)
    tg_username: Optional[str] = Field(None, max_length=255)
    whatsapp_phone: Optional[str] = Field(None, max_length=50)
    viber_phone: Optional[str] = Field(None, max_length=50)


class UserProfileResponse(BaseModel):
    """Schema for user profile response"""
    id: UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    country: Optional[str]
    phone: Optional[str]
    tg_phone: Optional[str]
    tg_username: Optional[str]
    whatsapp_phone: Optional[str]
    viber_phone: Optional[str]
    avatar_url: Optional[str]
    balance: Decimal
    two_fa_enabled: bool
    is_active: bool
    kyc_access: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("id")
    def serialize_id(self, v: UUID, _info):
        return str(v)

    @field_serializer("balance")
    def serialize_balance(self, v: Decimal, _info):
        return float(v)


class AvatarUploadResponse(BaseModel):
    """Schema for avatar upload response"""
    avatar_url: str
