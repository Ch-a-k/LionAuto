from pydantic import BaseModel, Field, ConfigDict
from typing import List

class ColorTypeCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z_]+$")

class ColorTypeRead(BaseModel):
    id: int
    code: str

    model_config = ConfigDict(from_attributes=True)

class ColorTypeListResponse(BaseModel):
    items: List[ColorTypeRead]