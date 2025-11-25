from uuid import UUID
from typing import Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models.deposit import DepositStatus, PaymentMethod


class DepositCreate(BaseModel):
    """Schema for creating a deposit"""
    amount: Decimal = Field(..., gt=0, description="Deposit amount, must be positive")
    payment_method: PaymentMethod
    payment_reference: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class DepositUpdate(BaseModel):
    """Schema for updating a deposit (admin only)"""
    status: Optional[DepositStatus] = None
    transaction_id: Optional[str] = None
    admin_notes: Optional[str] = None


class DepositResponse(BaseModel):
    """Schema for deposit response"""
    id: UUID
    user_id: UUID
    amount: Decimal
    currency: str
    status: DepositStatus
    payment_method: PaymentMethod
    transaction_id: Optional[str]
    payment_reference: Optional[str]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("id", "user_id")
    def serialize_uuid(self, v: UUID, _info):
        return str(v)

    @field_serializer("amount")
    def serialize_amount(self, v: Decimal, _info):
        return float(v)


class DepositListResponse(BaseModel):
    """Schema for paginated deposit list"""
    total: int
    page: int
    page_size: int
    deposits: list[DepositResponse]
