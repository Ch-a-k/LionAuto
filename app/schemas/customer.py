# app/schemas/customer.py
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.enums.customer_status import CustomerStatus

class KYCSubmitRequest(BaseModel):
    first_name: str
    last_name: str
    birth_date: str
    address: str

class KYCStatusResponse(BaseModel):
    status: CustomerStatus
    last_updated: datetime
    model_config = ConfigDict(from_attributes=True)