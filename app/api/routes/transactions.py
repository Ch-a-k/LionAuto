from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.models.user import User
from app.models.transaction import TransactionType
from app.api.dependencies import get_current_active_user
from app.schemas.transaction import (
    TransactionListResponse,
    BalanceResponse
)
from app.services.finance.transaction_service import TransactionService

router = APIRouter()


@router.get("/", response_model=TransactionListResponse)
async def get_my_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    transaction_type: Optional[TransactionType] = Query(None, alias="type"),
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's transaction history"""
    transactions, total = await TransactionService.get_user_transactions(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        transaction_type=transaction_type
    )

    return TransactionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        transactions=transactions
    )


@router.get("/balance", response_model=BalanceResponse)
async def get_my_balance(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's balance"""
    balance = await TransactionService.get_user_balance(current_user.id)

    return BalanceResponse(balance=balance)
