from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID
from typing import Optional

from app.models.user import User
from app.models.deposit import DepositStatus
from app.api.dependencies import get_current_active_user, admin_required
from app.schemas.deposit import (
    DepositCreate,
    DepositUpdate,
    DepositResponse,
    DepositListResponse
)
from app.services.finance.deposit_service import DepositService

router = APIRouter()


@router.post("/", response_model=DepositResponse, status_code=status.HTTP_201_CREATED)
async def create_deposit(
    deposit_data: DepositCreate,
    current_user: User = Depends(get_current_active_user)
):
    """Create a new deposit request"""
    try:
        deposit = await DepositService.create_deposit(
            user=current_user,
            amount=deposit_data.amount,
            payment_method=deposit_data.payment_method,
            payment_reference=deposit_data.payment_reference,
            description=deposit_data.description
        )
        return deposit
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=DepositListResponse)
async def get_my_deposits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[DepositStatus] = Query(None, alias="status"),
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's deposits"""
    deposits, total = await DepositService.get_user_deposits(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status_filter
    )

    return DepositListResponse(
        total=total,
        page=page,
        page_size=page_size,
        deposits=deposits
    )


@router.get("/{deposit_id}", response_model=DepositResponse)
async def get_deposit(
    deposit_id: UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Get deposit by ID"""
    from app.models.deposit import Deposit

    deposit = await Deposit.get_or_none(id=deposit_id, user_id=current_user.id)

    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found"
        )

    return deposit


# Admin routes
@router.put("/{deposit_id}/approve", response_model=DepositResponse)
async def approve_deposit(
    deposit_id: UUID,
    deposit_update: DepositUpdate,
    current_user: User = Depends(admin_required)
):
    """Approve a deposit (admin only)"""
    try:
        deposit = await DepositService.approve_deposit(
            deposit_id=deposit_id,
            transaction_id=deposit_update.transaction_id,
            admin_notes=deposit_update.admin_notes
        )
        return deposit
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{deposit_id}/reject", response_model=DepositResponse)
async def reject_deposit(
    deposit_id: UUID,
    deposit_update: DepositUpdate,
    current_user: User = Depends(admin_required)
):
    """Reject a deposit (admin only)"""
    try:
        deposit = await DepositService.reject_deposit(
            deposit_id=deposit_id,
            admin_notes=deposit_update.admin_notes
        )
        return deposit
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/admin/all", response_model=DepositListResponse)
async def get_all_deposits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[DepositStatus] = Query(None, alias="status"),
    user_id: Optional[UUID] = None,
    current_user: User = Depends(admin_required)
):
    """Get all deposits (admin only)"""
    from app.models.deposit import Deposit

    query = Deposit.all()

    if status_filter:
        query = query.filter(status=status_filter)

    if user_id:
        query = query.filter(user_id=user_id)

    total = await query.count()
    deposits = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)

    return DepositListResponse(
        total=total,
        page=page,
        page_size=page_size,
        deposits=deposits
    )
