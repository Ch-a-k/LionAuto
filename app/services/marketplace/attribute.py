from typing import List, Optional
from app.models.marketplace.attribute import AttributeType
from app.schemas.marketplace.attribute import AttributeTypeCreate
from tortoise.exceptions import IntegrityError

async def create_attribute_type(data: AttributeTypeCreate) -> AttributeType:
    try:
        return await AttributeType.create(code=data.code)
    except IntegrityError:
        raise ValueError(f"Attribute type '{data.code}' already exists")

async def get_attribute_type_by_code(code: str) -> Optional[AttributeType]:
    return await AttributeType.get_or_none(code=code)

async def get_all_attribute_types() -> List[AttributeType]:
    return await AttributeType.all()