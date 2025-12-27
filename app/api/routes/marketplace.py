from fastapi import APIRouter, Query, HTTPException
from app.schemas.marketplace.country import CountryCreate, CountryRead, CountryListResponse
from app.services.marketplace.country import create_country, get_country_by_code, get_all_countries
from app.schemas.marketplace.brand import BrandRead
from app.services.marketplace.brand import get_all_brands
from app.schemas.marketplace.model import CarModelListResponse, CarModelDetailRead
from app.services.marketplace.model import get_models_with_translations, get_car_model_by_id
from app.schemas.marketplace.language import LanguageRead
from app.services.marketplace.language import get_all_languages
from typing import List, Optional
import logging

router = APIRouter()

@router.get("/countries", response_model=CountryListResponse)  
async def list_countries(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    q: str | None = Query(None, description="Поиск по коду или названию")
):
    items, total = await get_all_countries(page=page, size=size, query=q)
    pages = (total + size - 1) // size

    country_reads = [CountryRead.model_validate(country) for country in items]

    return CountryListResponse(
        items=country_reads,
        total=total,
        page=page,
        size=size,
        pages=pages
    )

@router.get("/brands", response_model=list[BrandRead])
async def list_brands():
    brands = await get_all_brands()
    return [
        BrandRead(
            id=brand.id,
            name=brand.name
        )
        for brand in brands
    ]

@router.get("/languages", response_model=list[LanguageRead])
async def list_languages():
    return await get_all_languages()

@router.get("/car-models", response_model=CarModelListResponse)
async def list_car_models(
    lang: str = Query("en", min_length=2, max_length=2, pattern=r"^[a-z]{2}$"),
    brand_id: int | None = None,
    year: int | None = None,
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100)
):
    try:
        items, total = await get_models_with_translations(
            lang=lang,
            brand_id=brand_id,
            year=year,
            search=search,
            page=page,
            size=size
        )
        pages = (total + size - 1) // size
        return CarModelListResponse(items=items, total=total, page=page, size=size, pages=pages)
    except Exception as e:
        logging.exception("Error in list_car_models", e)
        raise HTTPException(status_code=500, detail="Failed to fetch models")

@router.get("/car-models/{model_id}", response_model=CarModelDetailRead)
async def get_car_model(
    model_id: int,
    lang: str = Query("en", min_length=2, max_length=2, pattern=r"^[a-z]{2}$")
):
    model_data = await get_car_model_by_id(model_id, lang)
    if not model_data:
        raise HTTPException(status_code=404, detail="Model not found")
    return model_data