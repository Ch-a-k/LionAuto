from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.security import OAuth2PasswordRequestForm
from app.models import RefreshToken, User
from app.schemas.user import UserResponse, TokenResponse
from app.api.dependencies import (
    get_current_user,
    get_current_active_user,
    admin_required,
    kyc_access_required,
    authenticate_user,
    create_access_token
)
from app.services.kyc.verification_service import VerificationService
from pydantic import BaseModel
from loguru import logger
from datetime import datetime, timedelta
import secrets

router = APIRouter()

REFRESH_TOKEN_EXPIRE_DAYS = 7

@router.get("/{user_id}/verification-status", response_model=UserResponse)
async def get_verification_status(user_id: int):
    try:
        return await VerificationService.get_status(user_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/me", response_model=UserResponse)
async def read_user_me(user: User = Depends(get_current_active_user)):
    return user

@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)

    scopes = ["user"]
    if await user.has_role("admin"):
        scopes.append("admin")
    if user.kyc_access:
        scopes.append("kyc")

    if form_data.scopes:
        requested_scopes = form_data.scopes.split()
        scopes = [s for s in scopes if s in requested_scopes]

    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id)},
        scopes=scopes
    )

    refresh_token_str = secrets.token_urlsafe(64)
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Сохраняем refresh token в базе
    await RefreshToken.create(user=user, token=refresh_token_str, expires_at=expires_at)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "JWT",
        "user_id": user.id
    }


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_access_token(data: RefreshTokenRequest = Body(...)):
    # Ищем refresh token в базе
    token_obj = await RefreshToken.get_or_none(token=data.refresh_token)
    if not token_obj or token_obj.is_expired():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = await token_obj.user
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")

    # Создаём новый access token (и по желанию новый refresh token)
    scopes = ["user"]
    if await user.has_role("admin"):
        scopes.append("admin")
    if user.kyc_access:
        scopes.append("kyc")

    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id)},
        scopes=scopes
    )

    return {
        "access_token": access_token,
        "refresh_token": data.refresh_token,  # либо можно сгенерировать новый и обновить в базе
        "token_type": "JWT",
        "user_id": user.id
    }

@router.post("/logout")
async def logout(user: User = Depends(get_current_user), data: RefreshTokenRequest = Body(...)):
    token_obj = await RefreshToken.get_or_none(token=data.refresh_token, user=user)
    if token_obj:
        await token_obj.delete()
    return {"message": "Logged out"}


@router.get("/admin")
async def admin_dashboard(admin: User = Depends(admin_required)):
    return {"message": "Admin dashboard"}

@router.post("/kyc/verify")
async def verify_kyc(user: User = Depends(kyc_access_required)):
    return {"message": "KYC verification started"}
