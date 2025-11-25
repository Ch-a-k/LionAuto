from uuid import UUID
from typing import Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_serializer

from app.models.transaction import TransactionType, TransactionStatus


class TransactionResponse(BaseModel):
    """Schema for transaction response"""
    id: UUID
    user_id: UUID
    transaction_type: TransactionType
    amount: Decimal
    currency: str
    status: TransactionStatus
    balance_before: Decimal
    balance_after: Decimal
    deposit_id: Optional[UUID]
    bid_id: Optional[UUID]
    reference_id: Optional[str]
    description: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("id", "user_id", "deposit_id", "bid_id")
    def serialize_uuid(self, v: Optional[UUID], _info):
        return str(v) if v else None

    @field_serializer("amount", "balance_before", "balance_after")
    def serialize_decimal(self, v: Decimal, _info):
        return float(v)


class TransactionListResponse(BaseModel):
    """Schema for paginated transaction list"""
    total: int
    page: int
    page_size: int
    transactions: list[TransactionResponse]


class BalanceResponse(BaseModel):
    """Schema for user balance response"""
    balance: Decimal
    currency: str = "USD"

    @field_serializer("balance")
    def serialize_balance(self, v: Decimal, _info):
        return float(v)
