from fastapi import APIRouter, Query
from app.schemas import (TransLiteral, VehicleTypeModelAddons, MakeModelAddons, ModelModelAddons,
                    SeriesModelAddons, YearCountResponse)

from app.models import VehicleType, Make, Model, Series, Lot, Lot1, Lot2 , Lot3 , Lot4, Lot5 , Lot6 , Lot7
from typing import List, Optional
from loguru import logger
from fastapi.exceptions import HTTPException
from fastapi import status
from tortoise.functions import Count
from app.services.translate_service import get_translation

router = APIRouter()

@router.get("/vehicle_types")
async def get_all_vehicle_types(language: TransLiteral = Query("en")):
    """
    Получает все типы транспортных средств, исключая 'other' и сортируя по количеству лотов
    """
    try:
        vehicle_types = await VehicleType.all()
        result = []
        
        for vt in vehicle_types:
            if vt.slug == "other":
                continue  # исключаем 'other'
            
            count = (
                await Lot1.filter(vehicle_type=vt).count() +
                await Lot2.filter(vehicle_type=vt).count() +
                await Lot3.filter(vehicle_type=vt).count() +
                await Lot4.filter(vehicle_type=vt).count() +
                await Lot5.filter(vehicle_type=vt).count() +
                await Lot6.filter(vehicle_type=vt).count() +
                await Lot7.filter(vehicle_type=vt).count()
            )

            item = {
                "id": vt.id,
                "name": vt.name,
                "slug": vt.slug,
                "icon_path": vt.icon_path,
                "icon_active": vt.icon_active,
                "icon_disable": vt.icon_disable,
                "counter": count
            }

            translated_value = await get_translation(
                field_name="vehicle_type", 
                original_value=vt.slug, 
                language=language
            )
            if translated_value:
                item["name"] = translated_value

            result.append(item)
        
        # Сортируем по убыванию количества
        result.sort(key=lambda x: x['counter'], reverse=True)
        
        return result
    except Exception as e:
        logger.error(f"Error getting vehicle types: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching vehicle types"
        )

@router.get("/makes", response_model=List[MakeModelAddons])
async def get_all_makes(
    vehicle_type_slug: str = Query("automobile", description="Slug типа транспортного средства"),
    language: str = Query("en", description="Язык для переводов (не используется в текущей реализации)")
) -> List[MakeModelAddons]:
    """
    Получает все марки (Make) для указанного типа транспортного средства
    """
    try:
        vehicle_type = await VehicleType.filter(slug=vehicle_type_slug).first()
        if not vehicle_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle type with slug '{vehicle_type_slug}' not found"
            )
        
        makes = await Make.filter(vehicle_type=vehicle_type).all()
        
        result = []
        for make in makes:
            count = await Lot1.filter(make=make).count()
            item = {
                "id": make.id,
                "name": make.name,
                "slug": make.slug,
                "vehicle_type_id": make.vehicle_type_id,
                "counter": count
            }
            result.append(MakeModelAddons(**item))
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting makes for vehicle type '{vehicle_type_slug}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching makes"
        )

@router.get("/models", response_model=List[ModelModelAddons])
async def get_all_models(
    make_slug: str = Query("audi", description="Slug марки транспортного средства"),
    language: str = Query("en", description="Язык для переводов (не используется в текущей реализации)")
) -> List[ModelModelAddons]:
    """
    Получает все модели (Model) для указанной марки транспортного средства
    """
    try:
        make_result = await Make.filter(slug=make_slug).first()
        if not make_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Make with slug '{make_slug}' not found"
            )
        
        models = await Model.filter(make=make_result).all()
        
        result = []
        for model in models:
            count = await Lot1.filter(model=model).count()
            item = {
                "id": model.id,
                "name": model.name,
                "slug": model.slug,
                "make_id": model.make_id,
                "counter": count
            }
            result.append(ModelModelAddons(**item))
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting models for make '{make_slug}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching models"
        )

@router.get("/series", response_model=List[SeriesModelAddons])
async def get_all_series(
    model_slug: str = Query("a4", description="Slug модели транспортного средства"),
    language: str = Query("en", description="Язык для переводов (не используется в текущей реализации)")
) -> List[SeriesModelAddons]:
    """
    Получает все серии (Series) для указанной модели транспортного средства
    """
    try:
        model = await Model.filter(slug=model_slug).first()
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model with slug '{model_slug}' not found"
            )
        
        series = await Series.filter(model=model).all()
        
        result = []
        for s in series:
            count = await Lot1.filter(series=s).count()
            item = {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "model_id": s.model_id,
                "counter": count
            }
            result.append(SeriesModelAddons(**item))
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting series for model '{model_slug}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching series"
        )

@router.get("/years", response_model=List[YearCountResponse])
async def get_available_years(
    vehicle_type_slug: Optional[str] = Query(None, description="Slug типа транспортного средства"),
    make_slug: Optional[str] = Query(None, description="Slug марки транспортного средства"),
    model_slug: Optional[str] = Query(None, description="Slug модели транспортного средства"),
    series_slug: Optional[str] = Query(None, description="Slug серии транспортного средства"),
    language: str = Query("en", description="Язык для переводов (не используется в текущей реализации)")
) -> List[YearCountResponse]:
    """
    Получает все доступные года из таблицы Lot с учетом переданных фильтров
    Возвращает список объектов с годом и количеством лотов для каждого года
    """
    try:
        query = Lot1.all()
        
        if vehicle_type_slug:
            vehicle_type = await VehicleType.filter(slug=vehicle_type_slug).first()
            if not vehicle_type:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Vehicle type with slug '{vehicle_type_slug}' not found"
                )
            query = query.filter(vehicle_type=vehicle_type)
        
        if make_slug:
            make = await Make.filter(slug=make_slug).first()
            if not make:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Make with slug '{make_slug}' not found"
                )
            query = query.filter(make=make)
        
        if model_slug:
            model = await Model.filter(slug=model_slug).first()
            if not model:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Model with slug '{model_slug}' not found"
                )
            query = query.filter(model=model)
        
        if series_slug:
            series = await Series.filter(slug=series_slug).first()
            if not series:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Series with slug '{series_slug}' not found"
                )
            query = query.filter(series=series)
        
        # Получаем года с количеством лотов для каждого года
        year_counts = await query.annotate(count=Count('id')).group_by("year").order_by("year").values("year", "count")
        
        # Преобразуем в список YearCountResponse
        return [
            YearCountResponse(year=item["year"], counter=item["count"])
            for item in year_counts
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting available years: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching available years"
        )