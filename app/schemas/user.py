from uuid import UUID
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    computed_field,   # <-- ВАЖНО: импортируем
)

from app.enums.auction_type import AuctionType


# --------- USERS ----------
class UserBase(BaseModel):
    email: str


class UserResponse(UserBase):
    id: UUID
    # эти поля Pydantic вытянет из ORM-модели User
    is_active: bool
    kyc_access: bool

    model_config = ConfigDict(from_attributes=True)

    # UUID -> str
    @field_serializer("id")
    def serialize_id(self, v: UUID, _info):
        return str(v)

    # вычисляемое поле, которое реально уйдет в JSON
    @computed_field  # type: ignore[misc]
    @property
    def is_verified(self) -> bool:
        # выбери свою бизнес-логику; сейчас маппинг на kyc_access
        return bool(getattr(self, "kyc_access", False))


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: Literal["JWT"] = Field(..., description="Type of the token")
    user_id: str = Field(..., description="ID of the authenticated user")


# --------- AUCTION ACCOUNTS ----------
class UserAuctionAccountCreate(BaseModel):
    auction_type: AuctionType
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)


class UserAuctionAccountUpdate(BaseModel):
    username: str | None = None
    password: str | None = None


class UserAuctionAccountResponse(BaseModel):
    id: int
    auction_type: AuctionType

    model_config = ConfigDict(from_attributes=True)
