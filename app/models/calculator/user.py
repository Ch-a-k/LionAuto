from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator
from app.schemas.user import Permissions

class CalculatorRole(models.Model):
    """
    Модель для уровней доступа (ролей).
    """
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
    description = fields.TextField(null=True)
    permissions = fields.JSONField(default=list)  # Список строковых разрешений
    
    class Meta:
        table = "calculator_roles"

    @property
    def is_superuser_role(self) -> bool:
        return Permissions.FULL_ACCESS in self.permissions

class CalculatorUser(models.Model):
    """
    Модель пользователя с полями для блокировки.
    """
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    full_name = fields.CharField(max_length=100)
    phone = fields.CharField(max_length=20)
    email = fields.CharField(max_length=100, unique=True)
    business_direction = fields.CharField(max_length=50, null=True)
    position = fields.CharField(max_length=50)
    office = fields.CharField(max_length=50, null=True)
    password_hash = fields.CharField(max_length=255)
    role = fields.ForeignKeyField("models.CalculatorRole", related_name="users")
    is_active = fields.BooleanField(default=True)
    banned_reason = fields.TextField(null=True)
    last_login = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "calculator_users"

    async def ban(self, reason: str = "Нарушение правил"):
        """Забанить пользователя."""
        self.is_active = False
        self.banned_reason = reason
        await self.save()

    async def unban(self):
        """Разбанить пользователя."""
        self.is_active = True
        self.banned_reason = None
        await self.save()

    async def get_permissions(self) -> list[str]:
        """Возвращает список всех доступов пользователя"""
        role: CalculatorRole = await self.role
        return role.permissions

    async def has_permission(self, permission: str) -> bool:
        """Проверяет наличие конкретного разрешения"""
        permissions = await self.get_permissions()
        return permission in permissions or Permissions.FULL_ACCESS in permissions

# Pydantic схемы
User_Pydantic = pydantic_model_creator(CalculatorUser, name="CalculatorUser")
UserIn_Pydantic = pydantic_model_creator(CalculatorUser, name="CalculatorUserIn", exclude_readonly=True)
Role_Pydantic = pydantic_model_creator(CalculatorRole, name="CalculatorRole")