from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from app.enums.auction_type import AuctionType


class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_verified: bool
    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: Literal["JWT"] = Field(..., description="Type of the token")
    user_id: int = Field(..., description="ID of the authenticated user")

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

    class Config:
        orm_mode = True
