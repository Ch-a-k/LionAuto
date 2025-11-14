from fastapi import APIRouter, Depends, HTTPException, Body, status
from fastapi.security import OAuth2PasswordRequestForm
from app.models import RefreshToken, User, Role
from app.models.user import UserRole 
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
from pydantic import BaseModel, EmailStr, Field
from loguru import logger
from datetime import datetime, timedelta
import secrets
from app.core.security.security import get_password_hash

router = APIRouter()

REFRESH_TOKEN_EXPIRE_DAYS = 7



class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate):
    """
    Регистрирует нового пользователя.

    - Проверяет, что email ещё не используется.
    - Хэширует пароль.
    - Создаёт пользователя.
    - Назначает роль basic_trader (если такая роль есть в БД).
    """
    # Проверяем, что email свободен
    existing = await User.get_or_none(email=payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Хэшируем пароль
    password_hash = get_password_hash(payload.password)

    # Создаём пользователя
    user = await User.create(
        email=payload.email,
        password_hash=password_hash,
        # is_active=True по умолчанию
    )

    # Назначаем роль basic_trader, если она существует
    try:
        basic_role = await Role.get_or_none(name=UserRole.basic_trader.value)
        if basic_role:
            await user.roles.add(basic_role)
    except Exception as e:
        logger.error(f"Failed to assign default role to user {user.email}: {e}")

    # Возвращаем пользователя (UserResponse преобразует ORM-модель)
    return user


@router.get("/{user_id}/verification-status", response_model=UserResponse)
async def get_verification_status(user_id: int):
    """
    Получает статус KYC-верификации пользователя.

    Args:
        user_id (int): Идентификатор пользователя.

    Returns:
        UserResponse: Объект пользователя со статусом верификации.

    Raises:
        HTTPException: 404 — если пользователь или его KYC-статус не найдены.
    """
    try:
        return await VerificationService.get_status(user_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def read_user_me(user: User = Depends(get_current_active_user)):
    """
    Возвращает информацию о текущем активном пользователе.

    Args:
        user (User): Пользователь, полученный через зависимость get_current_active_user.

    Returns:
        UserResponse: Данные текущего пользователя.
    """
    return user


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Выполняет аутентификацию пользователя и выдаёт пару токенов: access и refresh.

    После успешной проверки логина и пароля генерирует JWT-токен доступа
    с соответствующими ролями и правами, а также refresh-токен с ограниченным сроком жизни.

    Args:
        form_data (OAuth2PasswordRequestForm): Данные формы логина (username, password, scopes).

    Returns:
        TokenResponse: Ответ, содержащий access_token, refresh_token, тип токена и user_id.

    Raises:
        HTTPException: 
            401 — если имя пользователя или пароль неверны.
    """
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

    await RefreshToken.create(user=user, token=refresh_token_str, expires_at=expires_at)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "JWT",
        "user_id": str(user.id)
    }


class RefreshTokenRequest(BaseModel):
    """Схема тела запроса для обновления токена доступа."""
    refresh_token: str


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_access_token(data: RefreshTokenRequest = Body(...), user: User = Depends(get_current_active_user)):
    """
    Обновляет access_token с использованием refresh_token.

    Проверяет действительность refresh_token и пользователя, 
    затем создаёт новый access_token, сохраняя текущий refresh_token.

    Args:
        data (RefreshTokenRequest): Объект, содержащий refresh_token.

    Returns:
        TokenResponse: Новая пара токенов (access_token и текущий refresh_token).

    Raises:
        HTTPException:
            401 — если refresh_token недействителен или срок его действия истёк.
            401 — если пользователь неактивен.
    """
    token_obj = await RefreshToken.get_or_none(token=data.refresh_token)
    if not token_obj or token_obj.is_expired():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = await token_obj.user
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")

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
        "refresh_token": data.refresh_token,
        "token_type": "JWT",
        "user_id": str(user.id)
    }


@router.post("/logout")
async def logout(user: User = Depends(get_current_user), data: RefreshTokenRequest = Body(...)):
    """
    Выходит из системы, удаляя refresh_token пользователя.

    Args:
        user (User): Текущий пользователь, полученный через зависимость get_current_user.
        data (RefreshTokenRequest): Объект с refresh_token для удаления.

    Returns:
        dict: Сообщение о выходе из системы.

    Raises:
        HTTPException: 404 — если токен не найден для данного пользователя.
    """
    token_obj = await RefreshToken.get_or_none(token=data.refresh_token, user=user)
    if token_obj:
        await token_obj.delete()
    return {"message": "Logged out"}


@router.get("/admin")
async def admin_dashboard(admin: User = Depends(admin_required)):
    """
    Эндпоинт для доступа администратора к панели управления.

    Args:
        admin (User): Пользователь, проверенный через зависимость admin_required.

    Returns:
        dict: Сообщение о доступе к административной панели.

    Raises:
        HTTPException: 403 — если пользователь не является администратором.
    """
    return {"message": "Admin dashboard"}


@router.post("/kyc/verify")
async def verify_kyc(user: User = Depends(kyc_access_required)):
    """
    Инициирует процесс KYC-верификации для пользователя.

    Args:
        user (User): Пользователь, имеющий право на KYC-верификацию.

    Returns:
        dict: Сообщение о начале процесса верификации.

    Raises:
        HTTPException: 403 — если у пользователя нет доступа к KYC.
    """
    return {"message": "KYC verification started"}
