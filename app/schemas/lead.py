from pydantic import BaseModel, constr, EmailStr, ConfigDict
from pydantic_extra_types.phone_numbers import PhoneNumber
from typing import Annotated, Optional

class CreateLeadSchema(BaseModel):

    phone: PhoneNumber
    name: Optional[Annotated[str, constr(min_length=2)]] = None

    body_class: str | None = None
    # price: int | None = None
    year: str | None = None
    budget: str | None = None
    email: EmailStr | None = None
    comment: str | None = None

    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_term: str | None = None
    utm_content: str | None = None
    
    client_id: str | None = None

class LeadSchema(CreateLeadSchema):
    id: int

    model_config = ConfigDict(from_attributes=True)  # Важно!