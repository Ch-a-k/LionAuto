from app.models.user import User
from app.core.security.pass_hash import get_password_hash

class InitService:
    @staticmethod
    async def create_default_user():
        username = "admin@la.com"
        password = "securepassword123"
        email = "admin@la.com"
        
        # Проверяем, не существует ли уже пользователь
        if await User.exists(username=username):
            return None
            
        password_hash = get_password_hash(password)
        user = await User.create(
            username=username,
            email=email,
            password_hash=password_hash,
            is_admin=True,  # Делаем пользователя администратором
            kyc_access=True  # Даем доступ к KYC
        )
        return user