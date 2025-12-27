from typing import List, Optional
from app.models.marketplace.country import Country
from app.schemas.marketplace.country import CountryCreate
from tortoise.expressions import Q

async def get_all_countries(
    page: int = 1,
    size: int = 10,
    query: str | None = None
) -> tuple[list[Country], int]:
    offset = (page - 1) * size

    qs = Country.all()

    if query:
        qs = qs.filter(Q(code__icontains=query) | Q(name__icontains=query))

    total = await qs.count()
    items = await qs.limit(size).offset(offset)

    return items, total

async def create_country(data: CountryCreate) -> Country:
    return await Country.create(**data.dict())

async def get_country_by_code(code: str) -> Optional[Country]:
    return await Country.get_or_none(code=code.upper())