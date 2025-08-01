from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.models.user import User
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
from loguru import logger

router = APIRouter()

@router.get("/{user_id}/verification-status", response_model=UserResponse)
async def get_verification_status(user_id: int):
    try:
        return await VerificationService.get_status(user_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/me")
async def read_user_me(user: User = Depends(get_current_active_user)):
    return user

@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Получение JWT токена
    
    Параметры:
    - username: Логин пользователя
    - password: Пароль
    - scope: Необязательно (user, admin, kyc)
    """
    user = await authenticate_user(form_data.username, form_data.password)
    
    scopes = ["user"]
    if user.is_admin:
        scopes.append("admin")
    if user.kyc_access:
        scopes.append("kyc")
    
    # Фильтруем scopes, если они переданы в запросе
    if form_data.scopes:
        requested_scopes = form_data.scopes[0].split()
        scopes = [s for s in scopes if s in requested_scopes]
    
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},
        scopes=scopes
    )
    
    return {
        "access_token": access_token,
        "token_type": "JWT",
        "user_id": user.id
    }

@router.get("/admin")
async def admin_dashboard(admin: User = Depends(admin_required)):
    return {"message": "Admin dashboard"}

@router.post("/kyc/verify")
async def verify_kyc(user: User = Depends(kyc_access_required)):
    return {"message": "KYC verification started"}