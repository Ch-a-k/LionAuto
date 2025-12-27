from typing import List, Optional
from app.models.marketplace.color import ColorType
from app.schemas.marketplace.color import ColorTypeCreate
from tortoise.exceptions import IntegrityError

async def create_color_type(data: ColorTypeCreate) -> ColorType:
    try:
        return await ColorType.create(code=data.code)
    except IntegrityError:
        raise ValueError(f"Color type '{data.code}' already exists")

async def get_color_type_by_code(code: str) -> Optional[ColorType]:
    return await ColorType.get_or_none(code=code)

async def get_all_color_types() -> List[ColorType]:
    return await ColorType.all()