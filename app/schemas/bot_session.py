from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime

class BotSessionIn(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    storage_state_json: Dict[str, Any]

class BotSessionUpdate(BaseModel):
    storage_state_json: Dict[str, Any]

class BotSessionOut(BaseModel):
    username: str
    storage_state_json: Dict[str, Any]
    updated_at: datetime

class BotSessionListOut(BaseModel):
    items: list[BotSessionOut]
    total: int
    limit: int
    offset: int
