from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from tortoise.exceptions import DoesNotExist
from loguru import logger

from app.core.config import settings
from app.models.user import User
from app.core.security.pass_hash import verify_password

# Схемы аутентификации
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/kyc/token")  # Для эндпоинта /token
jwt_bearer = HTTPBearer()  # Для других защищённых роутов

class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[str] = None
    scopes: list[str] = []

async def authenticate_user(email: str, password: str) -> User:
    """Аутентификация пользователя по email и password"""
    try:
        user = await User.get(email=email)
        if not verify_password(password, user.password_hash):
            logger.warning(f"Failed login attempt for user {email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user"
            )
        return user
    except DoesNotExist:
        logger.warning(f"User not found: {email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

def create_access_token(
    data: dict, 
    expires_delta: Optional[timedelta] = None,
    scopes: list[str] = ["user"]
) -> str:
    """Создание JWT токена"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    
    to_encode.update({
        "exp": expire,
        "scopes": scopes
    })
    
    try:
        return jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm
        )
    except JWTError as e:
        logger.error(f"JWT encoding error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token creation failed"
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(jwt_bearer)
) -> User:
    """Получение текущего пользователя из JWT токена"""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("user_id")
        email = payload.get("sub")
        
        if user_id:
            user = await User.get(id=user_id)
        elif email:
            user = await User.get(email=email)
        else:
            raise credentials_exception
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user"
            )
        return user
    except (JWTError, DoesNotExist) as e:
        logger.error(f"Authentication error: {str(e)}")
        raise credentials_exception

async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    """Проверка активного пользователя"""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )
    return user

async def admin_required(user: User = Depends(get_current_user)) -> User:
    """Проверка прав администратора через роли"""
    if not await user.has_role("admin"):
        logger.warning(f"Admin access denied for user: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user

async def kyc_access_required(user: User = Depends(get_current_user)) -> User:
    """Проверка доступа к KYC"""
    if not user.kyc_access:
        logger.warning(f"KYC access denied for user: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="KYC access required"
        )
    return user

async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not await current_user.has_role("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return current_user
