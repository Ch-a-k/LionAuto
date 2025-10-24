from app.models import User, Role, Permission
from app.core.security.pass_hash import get_password_hash
from app.core.config import settings

class InitService:
    @staticmethod
    async def create_default_user():
        password = settings.PASSWORD
        email = settings.EMAIL
        
        # Проверяем, не существует ли уже пользователь
        if await User.exists(email=email):
            return None
            
        password_hash = get_password_hash(password)
        user = await User.create(
            email=email,
            password_hash=password_hash,
            is_admin=True,  # Делаем пользователя администратором
            kyc_access=True  # Даем доступ к KYC
        )
        return user
    
    @staticmethod
    async def init_roles_permissions():
        # Права
        perms = [
            {"name": "bid:create", "description": "Create bids"},
            {"name": "lot:view", "description": "View lots"},
            {"name": "lot:watch", "description": "Watch lots"},
            {"name": "auto_bid:manage", "description": "Manage autobid"},
            {"name": "admin:all", "description": "Full admin access"},
        ]

        for p in perms:
            await Permission.get_or_create(name=p["name"], defaults={"description": p["description"]})

        # Роли
        roles = {
            "admin": ["admin:all", "bid:create", "lot:view", "lot:watch", "auto_bid:manage"],
            "premium_trader": ["bid:create", "lot:watch", "auto_bid:manage"],
            "basic_trader": ["bid:create", "lot:view"],
            "readonly": ["lot:view"],
        }

        for role_name, perm_names in roles.items():
            role, _ = await Role.get_or_create(name=role_name)
            perms = await Permission.filter(name__in=perm_names)
            await role.permissions.clear()
            await role.permissions.add(*perms)
