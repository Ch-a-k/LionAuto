from passlib.context import CryptContext
import bcrypt
import logging

logger = logging.getLogger(__name__)

class PasswordHasher:
    def __init__(self):
        self._initialize_hasher()

    def _initialize_hasher(self):
        """Initialize the password hasher with fallback support"""
        try:
            # Test bcrypt directly first
            bcrypt.hashpw(b"test", bcrypt.gensalt())
            self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            self.active_scheme = "bcrypt"
        except Exception as e:
            logger.warning(f"BCrypt initialization failed: {str(e)}, falling back to argon2")
            try:
                self.pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
                self.active_scheme = "argon2"
            except Exception as e:
                logger.error(f"Argon2 initialization failed: {str(e)}, falling back to default")
                self.pwd_context = CryptContext(schemes=["default"], deprecated="auto")
                self.active_scheme = "default"
                logger.warning("Using default (less secure) scheme for password hashing")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Direct bcrypt password verification"""
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False

    def get_password_hash(self, password: str) -> str:
        """Direct bcrypt password hashing"""
        return bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

# Initialize the hasher at module level
hasher = PasswordHasher()

# Public interface
verify_password = hasher.verify_password
get_password_hash = hasher.get_password_hash