from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import List, Optional
from app.enums.auction_type import AuctionType

class LotSchema(BaseModel):
    id: UUID
    auction_type: AuctionType
    title: str
    description: Optional[str]
    start_price: Decimal
    auction_data: dict
    image_s3_keys: List[str]
    document_s3_keys: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # заменяет orm_mode = True
