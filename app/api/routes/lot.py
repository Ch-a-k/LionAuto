from fastapi import APIRouter, Query, HTTPException, status, Request
from app.tasks import get_refine_task, add_lot_task, process_batch_task
from app.schemas import (VehicleModel,  VehicleModelOther,
                         TaskResponseModel, TaskResponse, 
                        LotTypeCount, SpecialFilterLiteral,
                         LotHistoryResponse, TransLiteral, BatchTaskResponse,
                         LotSearchResponse, LotHistoryItem, VehicleModelResponse)
from fastapi.responses import JSONResponse
from app.services import (get_lot_by_lot_id_from_database, get_lot_by_id_from_database, 
                          get_similar_lots_by_id, serialize_lot, get_lots_count_by_vehicle_type,
                          search_lots, get_popular_brands_function, get_special_filtered_lots,
                          get_filtered_lots, create_cache_for_catalog, filter_copart_hd_images,
                          lot_to_dict, find_lots_by_price_range, generate_history_dropdown, json_safe)
from typing import List, Optional, Union, Dict, Any
from app.models import HistoricalLot, Lot
from app.services.translate_service import get_translation
from aiocache import caches
from loguru import logger
from datetime import datetime
from app.core.config import settings
import json
import uuid
import asyncio

router = APIRouter()
cache = caches.get("default")


@router.get("/refine")
async def get_refine_filters(
    request: Request,
    is_historical: Optional[bool] = Query(False),
    language: Optional[TransLiteral] = Query('en'),
    # Основные фильтры
    base_site: Optional[List[str]] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    min_odometer: Optional[int] = Query(None),
    max_odometer: Optional[int] = Query(None),

    # Фильтры по связанным моделям
    make_slug: Optional[List[str]] = Query(None),
    model_slug: Optional[List[str]] = Query(None),
    vehicle_type_slug: Optional[List[str]] = Query(None),
    damage_pr_slug: Optional[List[str]] = Query(None),
    damage_sec_slug: Optional[List[str]] = Query(None),
    fuel_slug: Optional[List[str]] = Query(None),
    drive_slug: Optional[List[str]] = Query(None),
    transmission_slug: Optional[List[str]] = Query(None),
    color_slug: Optional[List[str]] = Query(None),
    status_slug: Optional[List[str]] = Query(None),
    auction_status_slug: Optional[List[str]] = Query(None),
    body_type_slug: Optional[List[str]] = Query(None),
    series_slug: Optional[List[str]] = Query(None),
    title_slug: Optional[List[str]] = Query(None),
    seller_slug: Optional[List[str]] = Query(None),
    seller_type_slug: Optional[List[str]] = Query(None),
    document_slug: Optional[List[str]] = Query(None),
    document_old_slug: Optional[List[str]] = Query(None),
    cylinders: Optional[List[int]] = Query(None),
    engine: Optional[List[str]] = Query(None),
    engine_size: Optional[List[float]] = Query(None),

    # Дополнительные фильтры
    state: Optional[List[str]] = Query(None),
    is_buynow: Optional[bool] = Query(None),
    min_risk_index: Optional[float] = Query(None),
    max_risk_index: Optional[float] = Query(None),
    auction_date_from: Optional[datetime] = Query(None),
    auction_date_to: Optional[datetime] = Query(None),

    # Пагинация
    limit: int = Query(18, ge=1, le=1000),
    offset: int = Query(0, ge=0),

    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    # Сортировка
    sort_by: str = Query("auction_date", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    special_filter: List[SpecialFilterLiteral] = Query(None)
):
    """
    Запускает фоновую задачу для фильтрации лотов с возможностью получения агрегированной статистики.
    Использует кэш только если все дополнительные фильтры не заданы.
    """
    full_url = str(request.url)
    cached_result = await cache.get(f"{full_url}")
        
    if cached_result:
        
        result_dict = json.loads(cached_result)
        return result_dict
    def normalize_filter_value(value):
        """Конвертирует одиночные значения в списки для единообразия"""
        if value is None:
            return None
        if isinstance(value, (str, int, float)):
            return [value]
        return value

    # Все фильтры, кроме тех, что участвуют в кэш-ключе
    additional_filters = [
        min_year, max_year, min_odometer, max_odometer,
        make_slug, model_slug, damage_pr_slug, damage_sec_slug, fuel_slug,
        drive_slug, transmission_slug, color_slug, status_slug, body_type_slug,
        series_slug, title_slug, seller_slug, seller_type_slug, document_slug,
        document_old_slug, cylinders, engine, engine_size, state, auction_status_slug,
        is_buynow, min_risk_index, max_risk_index, auction_date_from, auction_date_to
    ]

    no_additional_filters = all(f is None for f in additional_filters)

    # Условие кэширования
    if (
    is_historical in [False, True] and
    language in ["ru", "en", "md", "ua", "kz", "pl", "ge", "de"] and
    normalize_filter_value(vehicle_type_slug) == ["automobile"] and
    limit == 18 and
    offset in [0,1,2,3,4,5,6,7] and
    sort_by in ["auction_date", "price", "year", "odometer", "created_at", "bid", "reserve_price"] and
    sort_order in ["desc","asc"] and
    no_additional_filters
):
        cache_key = f"{base_site[0] if base_site else ''}{settings.CACHE_KEY}{offset}{language}{'history' if is_historical else 'active'}{sort_by}{sort_order}"
        cached_result = await cache.get(cache_key)
        
        if cached_result:
            try:
                result_dict = json.loads(cached_result)
                
                # Обработка специальных фильтров
                if special_filter:
                    filter_key = f"{settings.CACHE_KEY}_{special_filter[0]}_{offset}_{language}_{"nonactive" if is_historical else "active"}"
                    logger.debug(f'Try get cached special filters: {filter_key}')
                    special_cached = await cache.get(filter_key)
                    
                    if special_cached:
                        special_data = json.loads(special_cached)
                        logger.success('Got cached special filters!')
                        # Убедимся, что данные имеют правильную структуру
                        if isinstance(special_data, dict):
                            result_dict["lots"] = special_data["results"].get("results", [])
                            result_dict["count"] = special_data["results"].get("count", 0)
                        else:
                            logger.warning("Unexpected special filter cache format")
                    else:
                        logger.debug(f'Get regenerated special filters')
                        lots_data = await get_special_filtered_lots(
                            is_historical=is_historical,
                            special_filter=special_filter,
                            limit=limit,
                            offset=offset,
                            language=language
                        )
                        result_dict["lots"] = lots_data.get("results", [])
                        result_dict["count"] = lots_data.get("count", 0)

                # Обработка фильтра по цене
                if min_price or max_price:
                    price_key = f"{settings.CACHE_KEY}_price_{min_price}_{max_price}_{offset}_{language}_{'history' if is_historical else 'active'}"
                    price_cached = await cache.get(price_key)
                    
                    if price_cached:
                        price_data = json.loads(price_cached)
                        result_dict["lots"] = price_data.get("results", [])
                        result_dict["count"] = price_data.get("count", 0)
                    else:
                        price_data = await find_lots_by_price_range(
                            min_price=min_price,
                            max_price=max_price,
                            is_historical=is_historical,
                            limit=limit,
                            offset=offset,
                            language=language
                        )
                        result_dict["lots"] = price_data.get("results", [])
                        result_dict["count"] = price_data.get("count", 0)

                # Кеширование деталей лотов
                if result_dict.get('lots'):
                    list_lot_ids = [lot['id'] for lot in result_dict['lots'] if isinstance(lot, dict)]
                    list_vin = [lot['vin'] for lot in result_dict['lots'] if isinstance(lot, dict) and lot.get('vin')]
                    asyncio.create_task(
                        create_cache_for_catalog(cache, language, list_lot_ids, list_vin, is_historical)
                    )
                
                return result_dict
                
            except Exception as e:
                logger.error(f"Error processing cached result: {str(e)}")
                logger.error(f"Cache key: {cache_key}, Cached data: {cached_result[:200] if cached_result else 'None'}")

    # Если не кэш — запускаем celery задачу
    try:
        auction_date_from_dt = datetime.fromisoformat(auction_date_from) if auction_date_from else None
        auction_date_to_dt = datetime.fromisoformat(auction_date_to) if auction_date_to else None
        
        result = await get_filtered_lots(
            cache=cache,
            full_url=full_url,
            language=language,
            is_historical=is_historical,
            base_site=base_site,
            min_year=min_year,
            max_year=max_year,
            min_odometer=min_odometer,
            max_odometer=max_odometer,

            # Фильтры по связанным моделям
            make_slug=make_slug,
            model_slug=model_slug,
            vehicle_type_slug=vehicle_type_slug,
            damage_pr_slug=damage_pr_slug,
            damage_sec_slug=damage_sec_slug,
            fuel_slug=fuel_slug,
            drive_slug=drive_slug,
            transmission_slug=transmission_slug,
            color_slug=color_slug,
            status_slug=status_slug,
            auction_status_slug=auction_status_slug,
            body_type_slug=body_type_slug,
            series_slug = series_slug,
            title_slug = title_slug,
            seller_slug = seller_slug,
            seller_type_slug = seller_type_slug,
            document_slug = document_slug,
            document_old_slug = document_old_slug,
            cylinders = cylinders,
            engine = engine,
            engine_size = engine_size,
            # Дополнительные фильтры
            state=state,
            # country=country,
            is_buynow=is_buynow,
            min_risk_index=min_risk_index,
            max_risk_index=max_risk_index,
            auction_date_from=auction_date_from_dt,
            auction_date_to=auction_date_to_dt,

            # Пагинация и сортировка
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        if special_filter:
            key = f"{settings.CACHE_KEY}_{special_filter[0]}_{offset}_{language}_{"nonactive" if is_historical else "active"}"
            cached_result = await cache.get(key)
            logger.debug(f'SPEACIAL FILTERS KEY TO GET: {key}')
            if cached_result:
                logger.debug('Get cached result by special filters')
                lots = json.loads(cached_result)
            else:
                lots = await get_special_filtered_lots(
                    is_historical=is_historical,
                    special_filter=special_filter,
                    limit=limit,
                    offset=offset,
                    language=language
                )
            result["lots"] = lots["results"]
            result["count"] = lots["count"]
        if min_price or max_price:
            key = f"{settings.CACHE_KEY}_min_price{min_price}max_price{max_price}{offset}"
            special_cached_result = await cache.get(key)
            if special_cached_result:
                lots = json.loads(special_cached_result)
                result["lots"] = lots["results"]["results"]
                result["count"] = lots["count"]["count"]
            else:
                lots = await find_lots_by_price_range(
                    min_price=min_price,
                    max_price=max_price,
                    is_historical=is_historical,
                    limit=limit,
                    offset=offset,
                    language=language
                )
                result["lots"] = lots["results"]
                result["count"] = lots["count"]
        list_lot_ids_to_cache = []
        list_vin = []
        for lot in result['lots']:
            list_lot_ids_to_cache.append(lot['id'])
            list_vin.append(lot['vin'])
        # asyncio.create_task(create_cache_for_catalog(cache, language,list_lot_ids_to_cache,list_vin, is_historical))
        return result
    except Exception as e:
        logger.error(f"Failed to start refine task: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start refinement task")


@router.post("/create", response_model=TaskResponseModel)
async def create_lot(lot: VehicleModel):
    """
    Запускает Celery-задачу по созданию лота и возвращает `task_id`.
    
    :param lot: Данные лота.
    :return: `task_id`, по которому клиент может проверить статус.
    """
    try:
        # Преобразуем модель в словарь, включая datetime в ISO формате
        lot_dict = lot.model_dump()
        # Запускаем Celery задачу
        task = add_lot_task.delay(lot_dict)
        
        return TaskResponseModel(
            status=True,
            message="Lot creation task started",
            task_id=task.id
        )

    except Exception as e:
        logger.error(f"Error creating lot: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error starting task: {str(e)}"
        )
    

@router.post("/lots/batch", response_model=BatchTaskResponse)
async def create_batch_lots(lots: List[VehicleModel|VehicleModelOther]):
    """
    Принимает список лотов и запускает ОДНУ задачу на обработку всей пачки
    """
    try:
        task_id = f"batch_{uuid.uuid4()}"
        lots_data = [lot.model_dump() for lot in lots]
        
        process_batch_task.apply_async(
            args=(lots_data,), 
            task_id=task_id
        )
        
        return BatchTaskResponse(
            task_id=task_id,
            total_lots=len(lots),
            message=f"Принято {len(lots)} лотов в обработку"
        )
        
    except Exception as e:
        logger.error(f"Batch create error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка запуска задачи: {str(e)}"
        )


@router.get("/similar_lots/{id}")
async def get_similar_lots(
    id: int,
    language: TransLiteral = Query("en"),
    limit: int = Query(5, description="Максимальное количество похожих лотов"),
):
    try:
        similar_lots = await get_similar_lots_by_id(
            lot_id=id,
            limit=limit,
            language=language,
        )

        results: List[Dict[str, Any]] = []

        for lot in similar_lots:
            # Прогружаем связи
            await lot.fetch_related(
                "vehicle_type", "make", "model", "series", "base_site",
                "damage_pr", "damage_sec", "keys", "odobrand", "fuel",
                "drive", "transmission", "color", "status", "auction_status",
                "body_type", "title", "seller_type", "seller", "document", "document_old",
            )

            # helper для reference-моделей
            def to_dict(obj):
                if obj is None:
                    return None
                if hasattr(obj, "_meta"):
                    data = {}
                    for field_name, field in obj._meta.fields_map.items():
                        if field_name.startswith("_"):
                            continue
                        data[field_name] = getattr(obj, field_name, None)
                    return data
                if isinstance(obj, dict):
                    return obj
                return {
                    k: v for k, v in obj.__dict__.items()
                    if not k.startswith("_")
                }

            # Основные поля лота
            lot_dict: Dict[str, Any] = {
                "id": lot.id,
                "lot_id": lot.lot_id,
                "odometer": lot.odometer,
                "price": lot.price,
                "reserve_price": lot.reserve_price,
                "bid": lot.bid,
                "current_bid": lot.current_bid,
                "auction_date": lot.auction_date.isoformat() if lot.auction_date else None,
                "cost_repair": lot.cost_repair,
                "year": lot.year,
                "cylinders": lot.cylinders,
                "state": lot.state,
                "vin": lot.vin,
                "engine": lot.engine,
                "engine_size": lot.engine_size,
                "location": lot.location,
                "location_old": lot.location_old,
                "country": lot.country,
                "image_thubnail": lot.image_thubnail,
                "is_buynow": lot.is_buynow,
                "link_img_hd": lot.link_img_hd,
                "link_img_small": lot.link_img_small,
                "link": lot.link,
                "risk_index": lot.risk_index,
                "created_at": lot.created_at.isoformat() if lot.created_at else None,
                "updated_at": lot.updated_at.isoformat() if lot.updated_at else None,
                "is_historical": lot.is_historical,
            }

            # Связаные модели + переводы
            related_fields = {
                "vehicle_type": lot.vehicle_type,
                "make": lot.make,
                "model": lot.model,
                "series": lot.series,
                "base_site": lot.base_site,
                "damage_pr": lot.damage_pr,
                "damage_sec": lot.damage_sec,
                "keys": lot.keys,
                "odobrand": lot.odobrand,
                "fuel": lot.fuel,
                "drive": lot.drive,
                "transmission": lot.transmission,
                "color": lot.color,
                "status": lot.status,
                "auction_status": lot.auction_status,
                "body_type": lot.body_type,
                "title": lot.title,
                "seller_type": lot.seller_type,
                "seller": lot.seller,
                "document": lot.document,
                "document_old": lot.document_old,
            }

            for field_name, related_obj in related_fields.items():
                if related_obj is not None:
                    rel_dict = to_dict(related_obj)
                    lot_dict[field_name] = rel_dict
                    if isinstance(rel_dict, dict):
                        slug_val = rel_dict.get("slug")
                        if slug_val:
                            translated_value = await get_translation(
                                field_name=field_name,
                                original_value=slug_val,
                                language=language,
                            )
                            if translated_value:
                                lot_dict[field_name]["name"] = translated_value
                else:
                    lot_dict[field_name] = None

            # COPART: чистим HD фотки
            try:
                base_site_slug = None
                base_site_data = lot_dict.get("base_site")
                if isinstance(base_site_data, dict):
                    base_site_slug = base_site_data.get("slug")
                if not base_site_slug and getattr(lot, "base_site", None) is not None:
                    base_site_slug = getattr(lot.base_site, "slug", None)

                if base_site_slug == "copart":
                    lot_dict["link_img_hd"] = filter_copart_hd_images(
                        lot_dict.get("link_img_hd")
                    )
            except Exception as e:
                print("ERROR processing copart HD images in /similar_lots:", e)

            # Можно подчистить None, если нужно
            results.append({k: v for k, v in lot_dict.items() if v is not None})

        return results

    except ValueError as e:
        # если исходный лот не найден
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/lots_by_price")
async def get_lots_by_price_range(
    language: TransLiteral = Query("en"),
    min_price: int = Query(0, description="Минимальная цена"),
    max_price: int = Query(1000000, description="Максимальная цена"),
    limit: int = Query(5, description="Максимальное количество лотов")
):
    try:
        # Получаем лоты по ценовому диапазону
        lots = await find_lots_by_price_range(
            min_price=min_price,
            max_price=max_price,
            limit=limit
        )
        
        results = []
        for lot in lots:
            # Явно загружаем все связанные данные
            await lot.fetch_related(
                "vehicle_type", "make", "model", "series", "base_site",
                "damage_pr", "damage_sec", "keys", "odobrand", "fuel",
                "drive", "transmission", "color", "status", "auction_status",
                "body_type", "title", "seller_type", "seller", "document", "document_old"
            )
            
            # Функция для преобразования ORM объектов в словари с исключением служебных полей
            def to_dict(obj):
                if obj is None:
                    return None
                if not hasattr(obj, "__dict__"):
                    return obj
                
                # Исключаем служебные поля Tortoise ORM
                exclude_fields = {
                    '_partial', '_custom_generated_pk', '_await_when_save', 
                    '_saved_in_db', '_fetched', '_custom_generated', '_state',
                    'vehicle_type_id', 'make_id'
                }
                
                return {
                    k: v for k, v in obj.__dict__.items()
                    if k not in exclude_fields
                }
            
            # Основные данные лота
            lot_dict = {
                "id": lot.id,
                "lot_id": lot.lot_id,
                "odometer": lot.odometer,
                "price": lot.price,
                "reserve_price": lot.reserve_price,
                "bid": lot.bid,
                "current_bid": lot.current_bid,
                "auction_date": lot.auction_date.isoformat() if lot.auction_date else None,
                "cost_repair": lot.cost_repair,
                "year": lot.year,
                "cylinders": lot.cylinders,
                "state": lot.state,
                "vin": lot.vin,
                "engine": lot.engine,
                "engine_size": lot.engine_size,
                "location": lot.location,
                "location_old": lot.location_old,
                "country": lot.country,
                "image_thubnail": lot.image_thubnail,
                "is_buynow": lot.is_buynow,
                "link_img_hd": lot.link_img_hd,
                "link_img_small": lot.link_img_small,
                "link": lot.link,
                "risk_index": lot.risk_index,
                "created_at": lot.created_at.isoformat(),
                "updated_at": lot.updated_at.isoformat(),
                "is_historical": lot.is_historical,
            }
            
            # Добавляем связанные объекты
            related_fields = {
                "vehicle_type": lot.vehicle_type,
                "make": lot.make,
                "model": lot.model,
                "series": lot.series,
                "base_site": lot.base_site,
                "damage_pr": lot.damage_pr,
                "damage_sec": lot.damage_sec,
                "keys": lot.keys,
                "odobrand": lot.odobrand,
                "fuel": lot.fuel,
                "drive": lot.drive,
                "transmission": lot.transmission,
                "color": lot.color,
                "status": lot.status,
                "auction_status": lot.auction_status,
                "body_type": lot.body_type,
                "title": lot.title,
                "seller_type": lot.seller_type,
                "seller": lot.seller,
                "document": lot.document,
                "document_old": lot.document_old
            }
            
            # Преобразуем связанные объекты
            for field_name, related_obj in related_fields.items():
                if related_obj is not None:
                    lot_dict[field_name] = to_dict(related_obj)
                    translated_value = await get_translation(
                        field_name=field_name, 
                        original_value=lot_dict[field_name]['slug'], 
                        language=language
                        )
                    if translated_value:
                        lot_dict[field_name]['name'] = translated_value
                else:
                    lot_dict[field_name] = None
            
            # Удаляем None значения для необязательных полей
            lot_dict = {k: v for k, v in lot_dict.items() if v is not None}
            
            results.append(lot_dict)
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/popular_brands")
async def get_popular_brands(
    limit: int = Query(48, description="Максимальное количество популярных брендов")
):
    """
    Возвращает список популярных автомобильных брендов.
    
    Популярность определяется на основе счетчика популярности (popular_counter).

    :param limit: Количество возвращаемых брендов (`int`, по умолчанию 48).
    :return: Список объектов `LotMarkResponse`, представляющих популярные марки авто.
    """
    popular_brands = await get_popular_brands_function(limit=limit)
    return popular_brands


@router.get("/search_car")
async def search_car(
    search_info: str = Query(..., description="VIN (17 символов), lot_id или название модели"),
    language: TransLiteral = Query(None, description="Язык для локализации")
):
    """
    Поиск автомобилей по VIN, lot_id или названию модели
    
    Args:
        search_info: Строка для поиска
        language: Язык для локализации результатов
        
    Returns:
        Список найденных лотов в формате LotSearchResponse
    """
    try:
        found_lots = await search_lots(search_info)
        
        # Преобразуем в Pydantic модель
        result = []
        for lot in found_lots:
            response = LotSearchResponse(
                id=lot.id,
                lot_id=lot.lot_id,
                image_thubnail=lot.image_thubnail or "",
                make=lot.make.name if lot.make else "",
                model=lot.model.name if lot.model else "",
                year=lot.year,
                lot_series=lot.series.name if lot.series else "",
                vin=lot.vin or "",
                auction=lot.base_site.name if lot.base_site else ""
            )
            result.append(response)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error in search: {str(e)}"
        )


@router.get("/more_lots")
async def get_more_lots(
    list_ids: List[int] = Query(..., description="Список ID лотов"),
    is_historical: bool = Query(False),
    language: TransLiteral = Query("en")
):
    """
    Возвращает лоты по списку ID
    """
    try:
        list_response = []
        for lot_id in list_ids:
            lot = await get_lot_by_id_from_database(lot_id, is_historical)
            if not lot:
                continue

            # Преобразуем лот в словарь
            lot_dict = await lot_to_dict(language,lot)
            list_response.append(lot_dict)
        
        # Применяем перевод, если нужно
        # if language != "en":
            # lot_dict = await translate_lot_fields(lot_dict, language)
        if len(list_response) == 0:
            raise HTTPException(status_code=404, detail="Лоты не были найдены!")
        return list_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cars_count", response_model=LotTypeCount)
async def cars_count(
    lot_type: str = Query("automobile", description="Тип транспортного средства"),
    is_historical: bool = Query(False, description="Искать в исторических лотах")
) -> LotTypeCount:
    """
    Получает количество лотов по типу транспортного средства
    
    Args:
        lot_type: Тип транспортного средства (automobile, motorcycle и т.д.)
        is_historical: Искать в таблице HistoricalLot вместо Lot
        
    Returns:
        Словарь с количеством лотов {"count": число}
    """
    try:
        count = await get_lots_count_by_vehicle_type(
            vehicle_type_slug=lot_type,
            include_historical=is_historical
        )
        return {"count": count}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving lot count: {str(e)}"
        )


@router.get("/move_lot/{id}")
async def move_lot_from_id(
    id: int,
    language: str
):
    """
    Перемещает лот in Historical, не трогать не убедившись в нужде
    """
    historical_lot = await Lot.move_to(id, HistoricalLot)

    # Преобразуем лот в словарь
    lot_dict = await serialize_lot(language,historical_lot)
        
    return lot_dict
    

@router.get("/id/{id}")
async def get_lot_by_id(
    id: int,
    is_historical: bool = Query(False),
    language: TransLiteral = Query("en")
):
    """
    Получает информацию о лоте по его внутреннему ID (PK с префиксом).
    """
    try:
        cache_key = f"{settings.CACHE_KEY}_lot_{id}_{language}_{'hist' if is_historical else 'cur'}"

        cached_result = await cache.get(cache_key)
        if cached_result:
            return json.loads(cached_result)

        # dict с переводами (уже, по идее, без ORM)
        lot_dict = await get_lot_by_id_from_database(
            id=id,
            language=language,
            is_historical=is_historical,
        )

        if not lot_dict:
            raise HTTPException(status_code=404, detail="Лот не найден")

        # Делаем JSON-безопасным
        safe_lot = json_safe(lot_dict)

        # Кладём в кеш уже безопасную структуру
        await cache.set(cache_key, json.dumps(safe_lot))

        # Возвращаем тоже безопасную
        return safe_lot

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/lot_id/{lot_id}")
async def get_lot_by_lot_id(
    lot_id: int, 
    is_historical: bool = Query(False), 
    language: TransLiteral = Query("en")
):
    """
    Получает полную информацию о лоте по его идентификатору (lot_id) со всеми полями из связанных таблиц.
    """
    try:
        lot = await get_lot_by_lot_id_from_database(lot_id, is_historical)
        if not lot:
            raise HTTPException(status_code=404, detail="Лот не найден")

        # Преобразуем лот в словарь
        # lot_dict = await serialize_lot(language,lot)
        
        # Применяем перевод, если нужно
        # if language != "en":
            # lot_dict = await translate_lot_fields(lot_dict, language)
            
        return lot
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{vin}")
async def get_history_car_by_vin(
    vin: str,
    is_historical: bool = False,
    language: TransLiteral = "en"
):
    # тут уже вернётся чистый dict с примитивами
    return await generate_history_dropdown(cache, vin, is_historical, language)


@router.get("/testcache")
async def test_cache(
):
    cached_result = await cache.get(f"all_active_count")
    cached_result1 = await cache.get(f"all_auction_active_count")
        
    if cached_result:
        
        result_dict = json.loads(cached_result)
    if cached_result1:
        result_dict1 = json.loads(cached_result1)

    return {
        "active_count": result_dict if cached_result else "No active count cached",
        "auction_active_count": result_dict1 if cached_result1 else "No auction active count cached"
    }




@router.get("/special_filtered")
async def get_catalog_by_special_filter(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    is_historical: bool = Query(False),
    special_filter: List[SpecialFilterLiteral] = Query(None),
    language: TransLiteral = Query('en')
):
    """
    Получение лотов с применением специальных фильтров
    (Минимальный код в эндпоинте)
    """
    return await get_special_filtered_lots(
        is_historical=is_historical,
        special_filter=special_filter,
        limit=limit,
        offset=offset,
        language=language
    )
