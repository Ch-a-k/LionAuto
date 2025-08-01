from tortoise import fields, models
from tortoise.exceptions import DoesNotExist
import secrets
from typing import Optional
from fastapi import HTTPException, status
from app.core.security.pass_hash import verify_password, get_password_hash

class User(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=255, unique=True)
    password_hash = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    is_admin = fields.BooleanField(default=False)
    kyc_access = fields.BooleanField(default=False)
    salt = fields.CharField(max_length=32, default=secrets.token_hex(16))
    
    class Meta:
        table = "users"
    
    @classmethod
    async def authenticate(cls, username: str, password: str) -> Optional['User']:
        """
        Аутентификация пользователя по username и password
        
        Args:
            username: Логин пользователя
            password: Пароль в чистом виде
            
        Returns:
            User: Модель пользователя или None если аутентификация не удалась
            
        Raises:
            HTTPException: Если пользователь неактивен
        """
        try:
            user = await cls.get(username=username)
            if not verify_password(password, user.password_hash):
                return None
                
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Inactive user"
                )
                
            return user
        except DoesNotExist:
            return None
    
    @classmethod
    async def create_user(cls, username: str, email: str, password: str, **kwargs):
        """
        Создание нового пользователя с хешированием пароля
        """
        password_hash = get_password_hash(password)
        user = await cls.create(
            username=username,
            email=email,
            password_hash=password_hash,
            **kwargs
        )
        return user