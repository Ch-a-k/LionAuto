from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.models import CalculatorRole, CalculatorUser
from app.schemas.user import TokenData
from app.core.security.security import verify_password
from app.core.config import settings
from loguru import logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def authenticate_user(email: str, password: str) -> CalculatorUser | None:
    """Enhanced authentication with proper error handling"""
    try:
        user = await CalculatorUser.get_or_none(email=email)
        if not user:
            return None
            
        # Verify password
        if not verify_password(password, user.password_hash):
            return None
            
        return user
    except Exception as e:
        logger.error(f"Authentication error for {email}: {str(e)}")
        return None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> CalculatorUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = await CalculatorUser.get_or_none(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: CalculatorUser = Depends(get_current_user)) -> CalculatorUser:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user