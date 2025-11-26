from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.models.user import User
from app.api.dependencies import get_current_active_user
from app.schemas.two_factor import (
    TwoFactorEnableResponse,
    TwoFactorVerifyRequest,
    TwoFactorDisableRequest,
    TwoFactorStatusResponse
)
from app.services.auth.two_factor_service import TwoFactorService

router = APIRouter()


@router.post("/enable", response_model=TwoFactorEnableResponse)
async def enable_two_factor(
    current_user: User = Depends(get_current_active_user)
):
    """Enable two-factor authentication"""
    try:
        result = await TwoFactorService.enable_2fa(current_user)

        return TwoFactorEnableResponse(
            secret=result["secret"],
            qr_code_url=result["qr_code_url"],
            backup_codes=result["backup_codes"]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/verify")
async def verify_two_factor(
    verify_data: TwoFactorVerifyRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Verify and activate two-factor authentication"""
    ip_address = request.client.host if request.client else None

    try:
        success = await TwoFactorService.verify_and_activate_2fa(
            user=current_user,
            code=verify_data.code,
            ip_address=ip_address
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )

        return {"message": "Two-factor authentication enabled successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/disable")
async def disable_two_factor(
    disable_data: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Disable two-factor authentication"""
    try:
        success = await TwoFactorService.disable_2fa(
            user=current_user,
            code=disable_data.code,
            password=disable_data.password
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )

        return {"message": "Two-factor authentication disabled successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/status", response_model=TwoFactorStatusResponse)
async def get_two_factor_status(
    current_user: User = Depends(get_current_active_user)
):
    """Get two-factor authentication status"""
    backup_codes_count = await TwoFactorService.get_backup_codes_count(current_user)

    return TwoFactorStatusResponse(
        two_fa_enabled=current_user.two_fa_enabled,
        backup_codes_count=backup_codes_count
    )
