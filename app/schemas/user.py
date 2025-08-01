from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

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