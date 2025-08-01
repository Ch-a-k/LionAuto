from pydantic import BaseModel, ConfigDict
from datetime import date

class CustomerInfoBase(BaseModel):
    first_name: str
    last_name: str
    birth_date: date
    country: str
    address: str
    city: str
    postal_code: str

class CustomerInfoCreate(CustomerInfoBase):
    pass

class CustomerInfoResponse(CustomerInfoBase):
    id: int
    model_config = ConfigDict(from_attributes=True)