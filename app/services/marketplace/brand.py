from typing import Optional, List
from app.models.marketplace.brand import Brand
from app.schemas.marketplace.brand import BrandCreate
from tortoise.exceptions import DoesNotExist

async def create_brand(data: BrandCreate) -> Brand:
    return await Brand.create(name=data.name)

async def get_all_brands() -> List[Brand]:
    return await Brand.all()

async def get_brand_by_name(name: str) -> Optional[Brand]:
    return await Brand.get_or_none(name=name)