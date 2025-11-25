from typing import Optional
from pydantic import BaseModel, Field


class TwoFactorEnableRequest(BaseModel):
    """Schema for enabling 2FA"""
    pass  # No input needed, will generate secret and QR code


class TwoFactorEnableResponse(BaseModel):
    """Schema for 2FA enable response"""
    secret: str
    qr_code_url: str
    backup_codes: list[str]


class TwoFactorVerifyRequest(BaseModel):
    """Schema for verifying 2FA code"""
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class TwoFactorDisableRequest(BaseModel):
    """Schema for disabling 2FA"""
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")
    password: str = Field(..., min_length=8)


class TwoFactorLoginRequest(BaseModel):
    """Schema for 2FA login"""
    email: str
    password: str
    two_fa_code: Optional[str] = Field(None, min_length=6, max_length=6)


class TwoFactorStatusResponse(BaseModel):
    """Schema for 2FA status response"""
    two_fa_enabled: bool
    backup_codes_count: int
