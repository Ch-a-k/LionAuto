from app.models import CalculatorUser
from fastapi import status, exceptions

async def check_permission(user: CalculatorUser, permission: str):
    if not await user.has_permission(permission):
        raise exceptions.HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав"
        )