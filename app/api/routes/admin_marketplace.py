from fastapi import APIRouter, Query, HTTPException, Body, status, File, UploadFile
from app.schemas.marketplace.country import CountryCreate, CountryRead
from app.services.marketplace.country import create_country, get_country_by_code
from app.schemas.marketplace.brand import BrandCreate, BrandRead
from app.services.marketplace.brand import create_brand, get_brand_by_name
from app.schemas.marketplace.model import CarModelCreate
from app.services.marketplace.model import create_car_model, delete_car_models, update_car_model
from app.schemas.marketplace.color import ColorTypeCreate, ColorTypeRead
from app.services.marketplace.color import create_color_type, get_all_color_types
from app.schemas.marketplace.attribute import AttributeTypeCreate, AttributeTypeRead
from app.services.marketplace.attribute import create_attribute_type, get_all_attribute_types
from app.schemas.marketplace.language import LanguageCreate, LanguageRead
from app.services.marketplace.language import create_language
from app.services.marketplace.model import save_model_images
from typing import List
import logging

router = APIRouter()

@router.post("/countries", response_model=CountryRead, status_code=status.HTTP_201_CREATED)
async def create_country_endpoint(data: CountryCreate):
    existing = await get_country_by_code(data.code)
    if existing:
        raise HTTPException(status_code=400, detail="Country with this code already exists")
    return await create_country(data)

@router.post("/brands", response_model=BrandRead, status_code=status.HTTP_201_CREATED)
async def create_brand_endpoint(data: BrandCreate):
    try:
        brand = await create_brand(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await get_brand_by_name(brand.name)

@router.post("/languages", response_model=LanguageRead, status_code=status.HTTP_201_CREATED)
async def create_language_endpoint(data: LanguageCreate):
    try:
        return await create_language(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/attribute-types", response_model=AttributeTypeRead, status_code=status.HTTP_201_CREATED)
async def create_attribute_type_endpoint(data: AttributeTypeCreate):
    try:
        return await create_attribute_type(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/attribute-types", response_model=list[AttributeTypeRead])
async def list_attribute_types():
    return await get_all_attribute_types()

@router.post("/color-types", response_model=ColorTypeRead, status_code=status.HTTP_201_CREATED)
async def create_color_type_endpoint(data: ColorTypeCreate):
    try:
        return await create_color_type(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/color-types", response_model=list[ColorTypeRead])
async def list_color_types():
    return await get_all_color_types()

@router.post("/car-models", status_code=status.HTTP_201_CREATED)
async def create_car_model_endpoint(data: CarModelCreate):
    try:
        model = await create_car_model(data)
        return {"id": model.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/car-models/{model_id}", response_model=dict)
async def update_car_model_endpoint(model_id: int, data: CarModelCreate):
    try:
        await update_car_model(model_id, data)
        return {"status": "updated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/car-models", status_code=status.HTTP_200_OK)
async def delete_car_models_endpoint(
    model_ids: List[int] = Body(..., embed=True)
):
    if not model_ids:
        raise HTTPException(status_code=400, detail="Model IDs list cannot be empty")
    
    deleted_count = await delete_car_models(model_ids)
    return {"deleted_count": deleted_count}

@router.post("/car-models/{model_id}/images", status_code=status.HTTP_201_CREATED)
async def upload_model_images(
    model_id: int,
    files: List[UploadFile] = File(..., description="List of image files (jpg, png, webp)"),
):
    try:
        saved_paths = await save_model_images(model_id, files)
        return {
            "uploaded_count": len(saved_paths),
            "image_paths": saved_paths
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to upload images")