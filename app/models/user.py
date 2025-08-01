import uuid
import secrets
from enum import Enum
from tortoise import fields, models
from tortoise.exceptions import DoesNotExist
from fastapi import HTTPException, status
from app.core.security.pass_hash import verify_password, get_password_hash
from typing import Optional

class UserRole(str, Enum):
    basic_trader = "basic_trader"
    admin = "admin"
    # добавь другие роли, если нужно

class User(models.Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    email = fields.CharField(max_length=255, unique=True)
    password_hash = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    kyc_access = fields.BooleanField(default=False)
    salt = fields.CharField(max_length=32, default=lambda: secrets.token_hex(16))
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    roles = fields.ManyToManyField("models.Role", related_name="users")

    class Meta:
        table = "users"

    @classmethod
    async def authenticate(cls, email: str, password: str) -> Optional['User']:
        try:
            user = await cls.get(email=email)
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

    async def has_role(self, role_name: str) -> bool:
        roles = await self.roles.all()
        return any(role.name == role_name for role in roles)
