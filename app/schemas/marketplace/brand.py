from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class BrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

class BrandRead(BaseModel):
    id: int
    name: str
    
    model_config = ConfigDict(from_attributes=True)