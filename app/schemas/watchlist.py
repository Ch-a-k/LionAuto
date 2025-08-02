from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class WatchlistEntrySchema(BaseModel):
    id: UUID
    user_id: UUID
    lot_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
