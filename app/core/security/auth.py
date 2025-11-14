from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status
from jose import jwt, JWTError
from app.core.config import settings
from app.models.user import User
from tortoise.exceptions import DoesNotExist

async def create_access_token(user_id: int, scopes: list[str] = ["user"]) -> dict:
    """
    Создает JWT токен для пользователя
    """
    user = await User.get(id=user_id)
    user_secret_key = settings.get_user_secret_key(user.id, user.salt)
    
    expire = datetime.now() + timedelta(minutes=settings.access_token_expire_minutes)
    
    payload = {
        "user_id": user.id,
        "sub": user.email,
        "scopes": scopes,
        "exp": expire
    }
    
    token = jwt.encode(
        payload,
        user_secret_key,
        algorithm=settings.algorithm
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id
    }

async def verify_token(token: str) -> User:
    """
    Проверяет JWT токен и возвращает пользователя
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Сначала получаем user_id без проверки подписи
        unverified = jwt.get_unverified_claims(token)
        user_id = unverified.get("user_id")
        if not user_id:
            raise credentials_exception
            
        # Получаем пользователя и генерируем его ключ
        user = await User.get(id=user_id)
        user_secret_key = settings.get_user_secret_key(user.id, user.salt)
        
        # Проверяем токен
        payload = jwt.decode(
            token,
            user_secret_key,
            algorithms=[settings.algorithm]
        )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user"
            )
            
        return user
        
    except (JWTError, DoesNotExist) as e:
        raise credentials_exception