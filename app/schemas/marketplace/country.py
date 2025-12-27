from pydantic import BaseModel, Field, ConfigDict
from app.schemas.common import PaginatedResponse

class CountryCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    name: str = Field(..., min_length=1, max_length=100)

class CountryRead(BaseModel):
    id: int
    code: str
    name: str

    model_config = ConfigDict(from_attributes=True)

class CountryListResponse(PaginatedResponse[CountryRead]):
    pass