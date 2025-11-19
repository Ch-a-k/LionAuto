from tortoise import Tortoise, functions
from tortoise.query_utils import Prefetch
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q, F
from tortoise.transactions import in_transaction
from typing import List, Optional, Dict, Any, Union
from tortoise.functions import Count
import httpx
from loguru import logger
from app.models import (Lot, BodyType, VehicleType, Make, Model, DamagePrimary, DamageSecondary,
                        Keys, OdoBrand, Fuel, Drive, Transmission, Color, Status, AuctionStatus,
                        HistoricalLot, LotWithouImage, LotHistoryAddons,
                        LotWithoutAuctionDate, Series, Seller, SellerType, Title, Document,
                        DocumentOld, BaseSite, LotOtherVehicle, LotBase, LotOtherVehicleHistorical,
                        Lot1, Lot2, Lot3, Lot4, Lot5, Lot6, Lot7)
from app.schemas import (VehicleModel, SpecialFilterLiteral, LotHistoryItem, VehicleModelOther,
                         VehicleModelResponse)
from datetime import datetime, timedelta, timezone, date, time
import asyncio
from app.services.translate_service import create_model_translations, get_translation
from app.core.config import settings
import json
import random


async def get_popular_brands_function(limit: int = 48):
    """
    Получает популярные бренды с сортировкой по popular_counter.
    Если popular_counter не используется, считает количество лотов для каждого бренда.
    """
    try:
        # Попробуем сначала получить по popular_counter
        popular_brands = await Make.filter(
            popular_counter__gt=0
        ).order_by(
            "-popular_counter"
        ).limit(limit).all()
        
        # Если нет результатов, попробуем альтернативный метод
        if not popular_brands:
            popular_brands = await Make.annotate(
                lots_count=Count('lots')
            ).filter(
                lots_count__gt=0
            ).order_by(
                "-lots_count"
            ).limit(limit).all()
            
            # Если все равно нет результатов, вернем любые бренды
            if not popular_brands:
                popular_brands = await Make.all().limit(limit)
                
        return popular_brands
        
    except Exception as e:
        logger.error(f"Error getting popular brands: {str(e)}")
        return []


async def add_sharding_lot(lot: Lot):
    async with in_transaction():
        original_id = lot.id
        logger.debug(original_id)
        old_lot: Lot = await get_lot_by_id_from_database(original_id, "en", False)
        # shard_number = Lot.get_shard_number(original_id)
        # logger.debug(shard_number)
        # LotModel: LotBase = Tortoise.apps.get("models")[f"LotShard{shard_number}"]
        vehicle_type = await VehicleType.get_or_create_by_name(old_lot.vehicle_type.name if old_lot.vehicle_type else None)
        make = await Make.get_or_create_by_name(old_lot.make.name if old_lot.make else None, vehicle_type=vehicle_type)
        model = await Model.get_or_create_by_name(old_lot.model.name if old_lot.model else None, make=make)
        
        series_name = old_lot.series.name if old_lot.series else None
        series = await Series.get_or_create_by_name(series_name, model=model) if series_name else None
        damage_pr = await DamagePrimary.get_or_create_by_name(old_lot.damage_pr.name if old_lot.damage_pr else None)
        damage_sec = await DamageSecondary.get_or_create_by_name(old_lot.damage_sec.name if old_lot.damage_sec else None)
        keys = await Keys.get_or_create_by_name(old_lot.keys.name if old_lot.keys else None)
        odobrand = await OdoBrand.get_or_create_by_name(old_lot.odobrand.name if old_lot.odobrand else None)
        fuel = await Fuel.get_or_create_by_name(old_lot.fuel.name if old_lot.fuel else None)
        drive = await Drive.get_or_create_by_name(old_lot.drive.name if old_lot.drive else None)
        transmission = await Transmission.get_or_create_by_name(old_lot.transmission.name if old_lot.transmission else None)
        
        color_name = old_lot.color.name if old_lot.color else None
        color = await Color.get_or_create_by_name(
            color_name if color_name in [
                "Blue", "Grey", "Black", 
                "Orange", "Turquoise", "Yellow", "Charcoal", "Silver", 
                "White", "Other", "Green", "Red", "Brown", "Purple", "Gold", 
                "Pink", "Beige", "Two Colors"
            ] else "Two Colors"
        )
        status = await Status.get_or_create_by_name(old_lot.status.name if old_lot.status else None)
        auction_status = await AuctionStatus.get_or_create_by_name(old_lot.auction_status.name if old_lot.auction_status else None)
        body_type = await BodyType.get_or_create_by_name(old_lot.body_type.name if old_lot.body_type else None)
        title = await Title.get_or_create_by_name(old_lot.title.name if old_lot.title else None)
        
        seller_type_name = (old_lot.seller_type.name if old_lot.seller_type else None)
        seller_type = await SellerType.get_or_create_by_name(
            seller_type_name.capitalize() if seller_type_name in [
                "Dealer", "Insurance companies", "Rental companies", 
                "Financing", "Third parties", "Insurance", "insurance", "dealer"
            ] else random.choice(["Third parties","Insurance companies"])
        )
        
        seller = await Seller.get_or_create_by_name(old_lot.seller.name if old_lot.seller else None)

        document = await Document.get_or_create_by_name(old_lot.document.name if old_lot.document else None)
        document_old = await DocumentOld.get_or_create_by_name(old_lot.document_old.name if old_lot.document_old else None)
        
        base_site_name = old_lot.base_site.name.lower() if old_lot.base_site else None
        if base_site_name in ['iaai', 'copart']:
            if base_site_name == "iaai":
                base_site_name = base_site_name.upper()
            else:
                base_site_name = base_site_name.capitalize()
            base_site = await BaseSite.get_or_create_by_name(base_site_name)
        lot_attrs = {
            'lot_id': old_lot.lot_id,
            'odometer': old_lot.odometer,
            'price': old_lot.price,
            'reserve_price': old_lot.reserve_price,
            'bid': old_lot.bid,
            'auction_date': old_lot.auction_date,
            'cost_repair': old_lot.cost_repair,
            'year': old_lot.year,
            'cylinders': old_lot.cylinders,
            'state': old_lot.state,
            'vin': old_lot.vin,
            'engine': old_lot.engine,
            'engine_size': old_lot.engine_size,
            'location': old_lot.location,
            'location_old': old_lot.location_old,
            'country': old_lot.country,
            'image_thubnail': old_lot.image_thubnail,
            'is_buynow': old_lot.is_buynow,
            'link_img_hd': old_lot.link_img_hd,
            'link_img_small': old_lot.link_img_small,
            'link': old_lot.link,
            'risk_index': old_lot.risk_index,
            'is_historical': old_lot.is_historical,
            'vehicle_type': vehicle_type,
            'make': make,
            'model': model,
            'series': series,
            'damage_pr': damage_pr,
            'damage_sec': damage_sec,
            'keys': keys,
            'odobrand': odobrand,
            'fuel': fuel,
            'drive': drive,
            'transmission': transmission,
            'color': color,
            'status': status,
            'auction_status': auction_status,
            'body_type': body_type,
            'title': title,
            'seller_type': seller_type,
            'seller': seller,
            'document': document,
            'document_old': document_old,
            'base_site': base_site
        }
        # await LotModel.create(**lot_attrs)


async def add_lot(vehicle_data: VehicleModel|VehicleModelOther) -> Optional[Dict[str, int]]:
    """
    Добавляет новый лот в базу данных, предварительно создавая/связывая все зависимые модели.
    
    :param vehicle_data: Данные лота в виде словаря
    :return: Словарь с id и lot_id созданного лота или None при ошибке
    """
    vin = vehicle_data.get('vin', 'UNKNOWN')
    try:
        async with in_transaction():
            
            # Создаем основной лот
            lot = await create_lot_with_relations(vehicle_data)
            if lot:
                
                return {
                    'id': lot.id,
                    'lot_id': lot.lot_id
                }
            
    except IntegrityError as e:
        logger.error(f"Integrity error adding lot {vin}: {str(e)}")
        return None
    except ValueError as e:
        logger.error(f"Value error adding lot {vin}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error adding lot {vin}: {str(e)}", exc_info=True)
        return None
    

async def update_lot(vehicle_data: VehicleModel|VehicleModelOther) -> Optional[Dict[str, int]]:
    """
    Добавляет новый лот в базу данных, предварительно создавая/связывая все зависимые модели.
    
    :param vehicle_data: Данные лота в виде словаря
    :return: Словарь с id и lot_id созданного лота или None при ошибке
    """
    vin = vehicle_data.get('vin', 'UNKNOWN')
    try:
        async with in_transaction():
            
            # Создаем основной лот
            lot = await update_lot_with_relations(vehicle_data)
            if lot:
                
                return {
                    'id': lot.id,
                    'lot_id': lot.lot_id
                }
            
    except IntegrityError as e:
        logger.error(f"Integrity error adding lot {vin}: {str(e)}")
        return None
    except ValueError as e:
        logger.error(f"Value error adding lot {vin}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error adding lot {vin}: {str(e)}", exc_info=True)
        return None
    

async def delete_lot(lot_id: int) -> Optional[Dict[str, int]]:
    """
    Добавляет новый лот в базу данных, предварительно создавая/связывая все зависимые модели.
    
    :param vehicle_data: Данные лота в виде словаря
    :return: Словарь с id и lot_id созданного лота или None при ошибке
    """
    try:
        async with in_transaction():
            
            # Создаем основной лот
            lot = await get_lot_by_lot_id_from_database(lot_id)
            await lot.delete()
            return True
            
    except IntegrityError as e:
        logger.error(f"Integrity error deleted lot {lot_id}: {str(e)}")
        return None
    except ValueError as e:
        logger.error(f"Value error deleted lot {lot_id}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error deleted lot {lot_id}: {str(e)}", exc_info=True)
        return None


async def generate_history_dropdown(cache, vin, is_historical, language):
    try:
        cached_result = await cache.get(f"{settings.CACHE_KEY}_vin_{vin}{language}")
        if cached_result:
            result_dict = json.loads(cached_result)
            return result_dict
        # Get historical data
        data = []
        lots_data = await search_lots(vin)
        
        for lot in lots_data:
            data.append({
                "id": lot.id,
                "lot_id": lot.lot_id,
                "sale_datetime": lot.auction_date,
                "auction_date": lot.auction_date,
                "auction": lot.base_site.name if lot.base_site else None,
                "image_thubnail": lot.image_thubnail,
                "odometer": lot.odometer,
                "bid": lot.bid,
                "final_bid": lot.bid,
                "status": lot.status,
                "color": lot.color.name if lot.color else None,
                "seller": lot.seller.name if lot.seller else None,
                "seller_type": lot.seller_type.name if lot.seller_type else None,
                "is_historical": lot.is_historical
            })
        logger.debug(lots_data)
        return {
            "last_bid": 0,
            "last_auction_date": None,
            "data": data
        }
        # data.append({
        #     "id": lot.id,
        #     "lot_id": lot.lot_id,
        #     "sale_datetime": lot.auction_date,
        #     "auction_date": lot.auction_date,
        #     "auction": lot.base_site.name if lot.base_site else None,
        #     "image_thubnail": lot.image_thubnail,
        #     "odometer": lot.odometer,
        #     "bid": lot.bid,
        #     "final_bid": api_data['data']['purchase_price'],
        #     "status": api_data['data']['sale_status'],
        #     "color": lot.color.name if lot.color else None,
        #     "seller": lot.seller.name if lot.seller else None,
        #     "seller_type": lot.seller_type.name if lot.seller_type else None,
        #     "is_historical": lot.is_historical
        # })

    except Exception as e:
        logger.error(f'Error in get history dropdown: {e}')

        return {
            "last_bid": 0,
            "last_auction_date": None,
            "data": []
        }


async def create_cache_for_catalog(cache,language,list_ids, list_vin, is_historical):
    for lot_id in list_ids:
        result = await get_lot_by_id_from_database(lot_id)
        if result:
            # Преобразуем объект Lot в словарь перед сериализацией
            # lot_dict = await lot_to_dict(language,result)
            lot = await serialize_lot(language,result)
            key = f"{settings.CACHE_KEY}_lot_{lot_id}{language}"
            await cache.set(key, json.dumps(lot), ttl=settings.CACHE_TTL + 180)
        
    # for vin in list_vin:
    #     result = await generate_history_dropdown(vin, is_historical, language)
    #     if result:
    #         key = f"{settings.CACHE_KEY}_vin_{vin}{language}"
    #         await cache.set(key, json.dumps(result), ttl=settings.CACHE_TTL)


async def get_lot_by_id_from_database(id: int, language: str = "ru", is_historical: bool = False) -> Optional[dict]:
    """
    Get lot from database with translations.
    Determines the correct table based on ID prefix.
    
    Args:
        id: Lot ID
        language: Translation language
    
    Returns:
        dict: Lot data with translations or None if not found
    """
    # Determine the model class based on ID prefix
    prefix = id // 10_000_000
    
    # Map prefixes to model classes
    prefix_to_model = {
        1: Lot,        # Main lots (will be routed to shards)
        2: HistoricalLot,
        3: LotWithoutAuctionDate,
        4: LotWithouImage,
        5: LotHistoryAddons,
        6: LotOtherVehicle,
        7: LotOtherVehicleHistorical,
        11: Lot1,      # Shards for main Lot
        12: Lot2,
        13: Lot3,
        14: Lot4,
        15: Lot5,
        16: Lot6,
        17: Lot7
    }
    
    # Get the appropriate model class
    model_class = prefix_to_model.get(prefix)
    
    if model_class is None:
        # If prefix is unknown, try all tables
        model_classes = [
            Lot, HistoricalLot, LotWithoutAuctionDate, 
            LotWithouImage, LotHistoryAddons, 
            LotOtherVehicle, LotOtherVehicleHistorical,
            Lot1, Lot2, Lot3, Lot4, Lot5, Lot6, Lot7
        ]
    else:
        model_classes = [model_class]
    
    # Try to find the lot in the appropriate table(s)
    for model in model_classes:
        lot = await model.filter(id=id).prefetch_related(
            "vehicle_type", "make", "model", "series", "base_site",
            "damage_pr", "damage_sec", "keys", "odobrand", "fuel",
            "drive", "transmission", "color", "status", "auction_status",
            "body_type", "title", "seller_type", "seller", "document", "document_old"
        ).first()
        
        if lot is not None:
            return lot
    
    return None


async def serialize_lot(language, lot: Lot) -> Dict[str, Any]:
    """
    Полностью преобразует объект лота и все связанные объекты в словарь.
    Включает все поля из основной таблицы и все поля из связанных таблиц.
    """
    # Основные поля лота
    lot_dict = {
        "id": lot.id,
        "lot_id": lot.lot_id,
        "odometer": lot.odometer,
        "price": lot.price,
        "reserve_price": lot.reserve_price,
        "bid": lot.bid,
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

    # Функция для сериализации связанных объектов
    async def serialize_related(obj):
        if obj is None:
            return None
        
        result = {
            "id": obj.id,
            "name": obj.name,
            "slug": obj.slug,
        }
        
        # Добавляем специфичные поля для разных моделей
        if isinstance(obj, VehicleType):
            result["icon_path"] = obj.icon_path
            result["icon_disable"] = obj.icon_disable
            result["icon_active"] = obj.icon_active
        elif isinstance(obj, Color):
            result["hex"] = obj.hex
        elif isinstance(obj, Status):
            result.update({
                "hex": obj.hex,
                "letter": obj.letter,
                "description": obj.description
            })
        elif isinstance(obj, Make):
            result.update({
                "popular_counter": obj.popular_counter,
                "icon_path": obj.icon_path
            })
        
        return result

    # Сериализуем все связанные объекты
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

    for field_name, related_obj in related_fields.items():
        if related_obj is not None:
            # Если объект уже загружен (благодаря prefetch_related)
            if isinstance(related_obj, (int, str)):
                # Если это ID (не должно происходить благодаря prefetch_related)
                lot_dict[field_name] = {"id": related_obj}
            else:
                lot_dict[field_name] = await serialize_related(related_obj)
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

    return lot_dict


async def get_lot_by_lot_id_from_database(
    lot_id: int, 
    is_historical: bool = False
) -> Optional[LotBase]:
    """
    Получает лот по lot_id из соответствующего шарда
    """
    try:
        lots = await Lot.query_across_shards(lot_id=lot_id)
        lot = lots[0] if lots else None  # Возьми первый элемент, если он есть
        # logger.debug(lot)

        if not lot:
            logger.warning(f"Lot {lot_id} not found in any shard")
        return lot

    except Exception as e:
        logger.error(f"Error getting lot by lot_id={lot_id}: {e}")
        return None


async def apply_special_filters(
    queryset,
    special_filters: List[SpecialFilterLiteral],
    is_historical: bool = False
):
    """
    Applies special filters to lots queryset
    """
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    next_week_start = today + timedelta(days=(7 - today.weekday()))
    next_week_end = next_week_start + timedelta(days=7)
    # Start with base filtering
    query = queryset.filter(is_historical=is_historical)
    if is_historical:
        auction_date_filter = None
    else:
        auction_date_filter = date.today()
    query = query.filter(auction_date__gte=auction_date_filter)

    for filter_name in special_filters:
        if filter_name == "buy_now":
            query = query.filter(is_buynow=True)
        
        elif filter_name == "keys":
            query = query.filter(keys__slug="yes")
        
        elif filter_name == "minimum_odometer":
            query = query.filter(odometer__gte=1, odometer__lte=50000)
            query = query.order_by("odometer")  # сортировка от меньшего к большему

        elif filter_name == "maximum_odometer":
            query = query.filter(odometer__gte=50000, odometer__lte=500000)
            query = query.order_by("-odometer")
        
        elif filter_name == "document_clean":
            query = query.filter(
                Q(document__slug="clean") | Q(document_old__slug="clean")
            )
        
        elif filter_name == "auction_date_today":
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)

            start_tomorrow = datetime.combine(tomorrow, time.min)  # начало завтрашнего дня 00:00:00
            start_day_after = datetime.combine(tomorrow + timedelta(days=1), time.min)
            query = query.filter(
                auction_date__gte=start_tomorrow,
                auction_date__lt=start_day_after
            )
        
        elif filter_name == "auction_date_tomorrow":
            query = query.filter(
                auction_date__gte=datetime.combine(tomorrow, datetime.min.time()),
                auction_date__lt=datetime.combine(tomorrow + timedelta(days=1), datetime.min.time())
            )
        
        elif filter_name == "auction_next_week":
            query = query.filter(
                auction_date__gte=datetime.combine(next_week_start, datetime.min.time()),
                auction_date__lt=datetime.combine(next_week_end, datetime.min.time())
            )

        elif filter_name == "run-and-drive":
            query = query.filter(status__slug="run-drive")
    
    return query


async def calculate_risk_index(
        year, 
        odometer, 
        auction_status,
        have_history,
        status
):
    """
    Асинхронно рассчитывает Risk Index для объекта Lot.

    :param year: Год выпуска машины.
    :param odometer: Пробег автомобиля.
    :param auction_status: Статус аукциона (например, Sold, Not Sold).
    :param have_history: История (True или False).
    :param status: Статус автомобиля (например, "Run & Drive", "Stationary").
    :return: Значение Risk Index (от 0 до 100).
    """

    # Устанавливаем значение статуса автомобиля
    if status == "Run & Drive":
        value_status = 1.0  # Максимальный риск индекс (машина заводится и едет)
    elif status == "Starts":
        value_status = 0.75  # Средний риск индекс (машина заводится, но не едет)
    elif status == "Stationary":
        value_status = 0.25  # Минимальный риск индекс (машина стоит)
    else:  # Unknown
        value_status = 0.5  # Средний риск индекс (неизвестно)

    # Рассчитываем возраст лота
    current_year = datetime.now().year
    age = current_year - year

    if age <= 3:
        age_value = 1.0  # Молодая машина
    elif 4 <= age <= 6:
        age_value = 0.7  # Средний возраст
    else:
        age_value = 0.4  # Старая машина

    # Рассчитываем значение для одометра
    if odometer is None or odometer == 0:
        value_odometer = 0.1  # Если одометр не указан или равен 0, минимальный индекс
    elif odometer < 50000:
        value_odometer = 1.0  # Очень маленький пробег
    elif odometer < 100000:
        value_odometer = 0.8  # Низкий пробег
    elif odometer < 200000:
        value_odometer = 0.6  # Средний пробег
    elif odometer < 300000:
        value_odometer = 0.4  # Большой пробег
    else:
        value_odometer = 0.2  # Очень большой пробег

    # Рассчитываем значение для истории автомобиля
    value_has_history = 1.0 if have_history else 0.5  # Если есть история, это повышает индекс

    # Устанавливаем значение для статуса аукциона
    if auction_status == "Not Sold":
        value_auction_status = 0.3  # Низкий индекс (не продано)
    elif auction_status == "Sold":
        value_auction_status = 1.0  # Высокий индекс (продано)
    else:
        value_auction_status = 0.5  # Средний индекс для других статусов

    # Суммируем все значения для расчета Risk Index
    risk_index = (
        (value_odometer * 15) +
        (value_has_history * 20) +
        (age_value * 10) +
        (value_status * 30) +
        (value_auction_status * 15) +
        25  # Для корректировки шкалы индекса
    )

    # Ограничиваем индекс значением от 0 до 100
    risk_index = min(100, max(0, risk_index))

    return risk_index

clean_titles = [
    "RI - CERTIFICATE OF TITLE",
    "CT - CERTIFICATE OF TITLE",
    "NJ - CERTIFICATE OF TITLE",
    "CA - CERTIFICATE OF TITLE (P)",
    "TX - CERTIFICATE OF TITLE (P)",
    "FL - CERTIFICATE OF TITLE (P)",
    "NY - CERTIFICATE OF TITLE (P)",
    "NH - CERTIFICATE OF TITLE (P)",
    "AR - CERTIFICATE OF TITLE",
    "WV - CERTIFICATE OF TITLE",
    "GA - CERTIFICATE OF TITLE (P)",
    "MA - CERTIFICATE OF TITLE (P)",
    "Clear (Illinois)",
    "Clear (Florida)",
    "Clear (Tennessee)",
    "Clear (New York)",
    "Clear (Missouri)",
    "Clear (Texas)",
    "Clear (Indiana)",
    "Clear (South Carolina)",
    "Clear (Colorado)",
    "Original (Ohio)",
    "Clear (Pennsylvania)",
    "Original (Texas)",
    "Clear (Virginia)",
    "Clear (Massachusetts)",
    "Clear (Alabama)",
    "Clear (Oregon)",
    "Regular Certificate (Iowa)",
    "Clear (Connecticut)",
    "Clear (New Jersey)",
    "CA - CERTIFICATE OF TITLE",
    "NH - CERTIFICATE OF TITLE",
    "MA - CERTIFICATE OF TITLE",
    "Clear (Montana)",
    "Clear (Hawaii)",
    "Clear (California)",
    "Clear (Nevada)",
    "Clear (Idaho)",
    "Clear (Arkansas)",
    "Clear (Maryland)",
    "Clear (North Carolina)",
    "Clear (Louisiana)",
    "Clear (Nebraska)",
    "Clear (Puerto Rico)",
    "Clear (Rhode Island)",
    "Clear (District Of Columbia)"
]

salvage_titles = [
    "KY - CERT OF TITLE-SALVAGE",
    "MO - SALVAGE CERTIFICATE OF TITLE",
    "HI - CERTIFICATE OF SALVAGE",
    "TX - SALVAGE VEHICLE TITLE (P)",
    "NJ - CERT OF TITLE-SALVAGE",
    "IL - SALVAGE CERTIFICATE",
    "GA - CERT OF TITLE-SALVAGE",
    "FL - CERT OF TITLE SLVG REBUILDABLE",
    "NH - CERT OF TITLE-SALVAGE",
    "UT - SALVAGE CERTIFICATE",
    "ID - SALVAGE CERTIFICATE OF TITLE",
    "TN - SALVAGE CERTIFICATE",
    "NV - SALVAGE TITLE",
    "AR - CERT OF TITLE-SALVAGE",
    "SC - CERT OF TITLE-SALVAGE",
    "IA - CERT OF TITLE-SALVAGE TITLE",
    "CA - SALVAGE CERTIFICATE (P)",
    "MN - CERT OF TITLE-SALVAGE",
    "IN - CERT OF TITLE-SALVAGE TITLE",
    "AZ - CERT OF TITLE - SALVAGE",
    "RI - SALVAGE CERTIFICATE OF TITLE",
    "CT - CERT OF TITLE-SALVAGE",
    "OR - SALVAGE TITLE CERTIFICATE",
    "NY - MV-907A SALVAGE CERTIFICATE",
    "Salvage (South Carolina)",
    "Salvage Title (Texas)",
    "VA - CERT OF TITLE - SALVAGE",
    "Salvage (North Carolina)",
    "AL - CERT OF TITLE-SALVAGE TITLE",
    "GA - CERT OF TITLE-REBUILT SALVAGE",
    "MD - CERT OF SALVAGE > 75% DAMAGE",
    "MS - CERTIFICATE OF TITLE - JUNK",
    "ON - PERMIT SALVAGE",
    "PA - CERTIFICATE OF SALVAGE",
    "NC - SALVAGE CERTIFICATE OF TITLE",
    "LA - CERT OF TITLE-SALVAGE FLOOD",
    "MA - CERT OF TITLE-SALVAGE",
    "KY - CERT OF TITLE-SALVAGE WATER",
    "GA - CERT OF TITLE-FLOOD SALVAGE",
    "MI - CERT OF TITLE-SALVAGE VEHICLE",
    "Salvage (Georgia)",
    "Salvage - Greater Than 75% (Maryland)",
    "Salvage (Indiana)",
    "Salvage Certificate (West Virginia)",
    "Salvage (Illinois)",
    "Salvage (Tennessee)",
    "Salvage (New Jersey)",
    "Salvage (Missouri)",
    "Salvage (Delaware)",
    "Salvage (Maryland)",
    "Salvage (Massachusetts)",
    "Salvage (Kentucky)",
    "Salvage (Arkansas)",
    "Salvage (Kansas)",
    "Salvage (Ohio)",
    "Salvage (Colorado)",
    "Salvage (Montana)",
    "Salvage - 75% Or Less (Maryland)",
    "Salvage (Oklahoma)",
    "Salvage (Idaho)",
    "Salvage (Maine)",
    "Salvage Certificate (Hawaii)",
    "Salvage (Oregon)",
    "Salvage Certificate (Texas)",
    "Salvage (Utah)",
    "Salvage (Virginia)",
    "Salvage (Arizona)",
    "Salvage (Louisiana)",
    "Salvage (Pennsylvania)",
    "Salvage (Michigan)",
    "Salvage (Mississippi)",
    "Salvage (North Dakota)",
    "Salvage (Nevada)",
    "Salvage (Vermont)",
    "Salvage (Nebraska)",
    "Salvage (Wisconsin)",
    "Salvage (Rhode Island)",
    "Salvage (Connecticut)",
    "Salvage (New Hampshire)",
    "Salvage (Wyoming)",
    "Salvage (New Mexico)",
    "Salvage (Florida)",
    "Salvage (District Of Columbia)"
]

non_repairable_titles = [
    "TX - NONREPAIRABLE TITLE",
    "Non-Repairable (Maryland)",
    "Non-Repairable (California)",
    "Non-Repairable (Texas)",
    "Non-Repairable (Arizona)",
    "Non-Repairable Certificate (West Virginia)",
    "Non-Repairable (Tennessee)",
    "Non-Repairable (Kansas)",
    "Non-Repairable (Nevada)",
    "Non-Repairable (Utah)",
    "Non-Repairable (Virginia)",
    "Non-Repairable (Colorado)",
    "Non-Repairable (Pennsylvania)",
    "Non-Repairable (District Of Columbia)",
    "Non-Repairable (New Mexico)",
    "Non-Repairable (Arkansas)",
    "Non-Repairable (Mississippi)"
]

other_titles = [
    "CA - APP FOR DUP CLEAN OR AC (P)",
    "Mv-907A (New York)",
    "Rebuilt (Indiana)",
    "CA - APP FOR DUP CLEAN OR AC",
    "CA - LIEN PAPERS-CLEAN OR AC",
    "Bill Of Sale (Georgia)",
    "Bill Of Sale (Kentucky)",
    "Permit To Sell (Louisiana)",
    "Clear-Dealer Only (California)",
    "Repo Paperwork (New York)",
    # ... (остальные документы, не попавшие в первые 3 категории)
]

VEHICLE_TYPE_NORMALIZER = {
    "ATV": "ATVs",
    "Jet Sky": "Jet Skis",
    "Boat": "Boats",
    "Truck": "Pickup Trucks",  # Можешь поменять на "Heavy Duty Trucks" при необходимости
    "Mobile Home": "RV",
    "Industrial Equipment": "Special equipment",
    "Watercraft": "Jet Skis",  # Или "Boats" — в зависимости от смысла
    "Automobile": "Automobile",
    "Motorcycle": "Motorcycle",
    "Trailers": "Trailers",
    "Bus": "Bus"
}

COLOR_CHOICES = ["Blue", "Grey", "Black", "Orange", "Turquoise", "Yellow", 
                "Charcoal", "Silver", "White", "Other", "Green", "Red", 
                "Brown", "Purple", "Gold", "Pink", "Beige", "Two Colors"]

STATUS_MAPPING = {
    "Run & Drive": "Run & Drive",
    "Enhanced Vehicle": "Run & Drive",
    "Engine Start Program": "Starts",
    "Does not Start": "Stationary"
}

SELLER_TYPES = ["Dealer", "Insurance companies", "Rental companies", 
               "Financing", "Third parties"]

def classify_title(title):
    title_lower = title.lower()
    
    if any(phrase in title_lower for phrase in ["non-repairable", "nonrepairable", "irreparable", "destruction", "parts only"]):
        return "Non-Repairable"
    elif any(phrase in title_lower for phrase in ["salvage", "rebuild", "flood", "water", "junk", "scrap"]):
        return "Salvage"
    elif ("certificate of title" in title_lower and not any(phrase in title_lower for phrase in ["salvage", "rebuild"])):
        return "Clean"
    elif any(phrase in title_lower for phrase in ["clean", "clear", "original", "regular"]):
        return "Clean"
    else:
        return "Other"

async def create_lot_with_relations(lot_data: dict) -> Optional[LotBase]:
    """
    Создает лот в базе данных со всеми связанными моделями,
    с автоматическим определением шарда для сохранения.
    Если vehicle_type.slug != 'automobile', добавляет только в LotOtherVehicle.
    """
    try:
        current_date = datetime.now().date()
        auction_date_str = lot_data.get('auction_date') or lot_data.get('sale_date')
        auction_date_passed = False
        auction_date = None
        
        # Обработка даты аукциона
        if auction_date_str:
            if isinstance(auction_date_str, datetime):
                auction_date = auction_date_str
            elif isinstance(auction_date_str, str):
                try:
                    auction_date = datetime.strptime(auction_date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
                except ValueError:
                    try:
                        auction_date = datetime.strptime(auction_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                    except ValueError as e:
                        logger.error(f"Error parsing date {auction_date_str}: {e}")
            
            if auction_date:
                auction_date_passed = auction_date.date() < current_date

        # Обработка изображений
        image_thumbnail = None
        if lot_data.get('link_img_small'):
            image_thumbnail = lot_data['link_img_small'][0]
        elif lot_data.get('link_img_hd'):
            image_thumbnail = lot_data['link_img_hd'][0]

        async with in_transaction():
            # 1. Проверяем наличие лота во всех таблицах
            tables_to_check = [
                Lot, LotWithoutAuctionDate, LotWithouImage,
                HistoricalLot, LotHistoryAddons, LotOtherVehicle, LotOtherVehicleHistorical
            ]
            
            existing_lot = None
            for model in tables_to_check:
                existing = await model.filter(
                    lot_id=lot_data['lot_id'],
                    vin=lot_data['vin']
                ).first()
                if existing:
                    existing_lot = existing
                    break

            if existing_lot:
                logger.info(f"Lot already exists -> {existing_lot.vin}:{existing_lot.lot_id}")
                return existing_lot

            # 2. Определяем целевую модель для сохранения
            vin = lot_data.get('vin', '')
            vehicle_type_name = VEHICLE_TYPE_NORMALIZER.get(
                lot_data['vehicle_type'], 
                lot_data['vehicle_type']
            )
            
            if vehicle_type_name.startswith("Snow"):
                vehicle_type_name = "Snowmobile"
            elif vehicle_type_name.startswith("Dirt") or vehicle_type_name.startswith("Bike"):
                vehicle_type_name = "Dirt Bikes"
            
            vehicle_type = await VehicleType.get_or_create_by_name(vehicle_type_name)
            
            # Выбор модели на основе типа транспортного средства
            if vehicle_type.slug != 'automobile':
                LotModel = LotOtherVehicle
                if auction_date_passed:
                    LotModel = LotOtherVehicleHistorical
            else:
                if len(vin) != 17:
                    LotModel = LotOtherVehicle
                else:
                    if auction_date is None:
                        LotModel = LotWithoutAuctionDate
                    elif auction_date_passed:
                        LotModel = HistoricalLot
                    else:
                        LotModel = Lot

                if image_thumbnail is None and LotModel not in {LotOtherVehicle, HistoricalLot}:
                    LotModel = LotWithouImage

            # 3. Получаем правильный шард для сохранения
            shard_class = await LotModel.get_shard_for_new_record()

            # 4. Подготовка связанных моделей
            try:
                make = await Make.get_or_create_by_name(lot_data['make'], vehicle_type=vehicle_type)
                model = await Model.get_or_create_by_name(lot_data['model'], make=make)
                
                series_name = lot_data.get('series', None)
                series = await Series.get_or_create_by_name(series_name, model=model) if series_name else None
                
                await create_model_translations("vehicle_type", vehicle_type)
            except Exception as e:
                logger.error(f"Error creating vehicle hierarchy: {str(e)}")
                return None

            # Подготовка опциональных связанных моделей
            damage_pr = await DamagePrimary.get_or_create_by_name(lot_data.get('damage_pr')) if lot_data.get('damage_pr') else None
            damage_sec = await DamageSecondary.get_or_create_by_name(lot_data.get('damage_sec')) if lot_data.get('damage_sec') else None
            keys = await Keys.get_or_create_by_name(lot_data.get('keys')) if lot_data.get('keys') else None
            odobrand = await OdoBrand.get_or_create_by_name(lot_data.get('odobrand')) if lot_data.get('odobrand') else None
            fuel = await Fuel.get_or_create_by_name(lot_data.get('fuel')) if lot_data.get('fuel') else None
            drive = await Drive.get_or_create_by_name(lot_data.get('drive')) if lot_data.get('drive') else None
            transmission = await Transmission.get_or_create_by_name(lot_data.get('transmission')) if lot_data.get('transmission') else None
            
            color = await Color.get_or_create_by_name(
                lot_data.get('color', 'Other') if lot_data.get('color') in COLOR_CHOICES else "Two Colors"
            )
            
            status_name = STATUS_MAPPING.get(lot_data.get('status'), lot_data.get('status'))
            status = await Status.get_or_create_by_name(status_name) if status_name else None
                
            auction_status = await AuctionStatus.get_or_create_by_name(lot_data.get('auction_status','Not sold'))
            body_type = await BodyType.get_or_create_by_name(lot_data.get('body_type')) if lot_data.get('body_type') else None
            title = await Title.get_or_create_by_name(lot_data.get('title')) if lot_data.get('title') else None
            
            seller_type = await SellerType.get_or_create_by_name(
                (lot_data.get('seller_type') or '').capitalize() if lot_data.get('seller_type') in SELLER_TYPES else "Third parties"
            )
            
            seller = await Seller.get_or_create_by_name(lot_data.get('seller')) if lot_data.get('seller') else None
            
            document_short_type = classify_title(lot_data.get('document_old')) if lot_data.get('document_old') else "Unknown"
            document = await Document.get_or_create_by_name(document_short_type)
            document_old = await DocumentOld.get_or_create_by_name(lot_data.get('document_old')) if lot_data.get('document_old') else None
            
            base_site = None
            if base_site_name := lot_data.get('base_site', '').lower():
                if base_site_name in ['iaai', 'copart']:
                    base_site_name = base_site_name.upper() if base_site_name == "iaai" else base_site_name.capitalize()
                    base_site = await BaseSite.get_or_create_by_name(base_site_name)

            # Создаем переводы для связанных моделей
            for rel_model, rel_instance in [
                ("damage_pr", damage_pr),
                ("document", document),
                ("damage_sec", damage_sec),
                ("keys", keys),
                ("odobrand", odobrand),
                ("fuel", fuel),
                ("drive", drive),
                ("transmission", transmission),
                ("color", color),
                ("status", status),
                ("auction_status", auction_status),
                ("body_type", body_type),
                ("seller_type", seller_type)
            ]:
                if rel_instance:
                    await create_model_translations(rel_model, rel_instance)

            # Расчет risk_index
            risk_index = await calculate_risk_index(
                year=lot_data.get('year'),
                odometer=lot_data.get('odometer'),
                auction_status=auction_status.name if auction_status else None,
                status=status.name if status else None,
                have_history=False
            )

            # 5. Подготовка данных для сохранения
            lot_attrs = {
                'lot_id': lot_data['lot_id'],
                'odometer': lot_data.get('odometer'),
                'price': lot_data.get('price'),
                'reserve_price': lot_data.get('reserve_price'),
                'bid': lot_data.get('bid', 0),
                'auction_date': auction_date,
                'cost_repair': lot_data.get('cost_repair'),
                'year': lot_data['year'],
                'cylinders': lot_data.get('cylinders'),
                'state': lot_data['state'],
                'vin': lot_data['vin'],
                'engine': lot_data.get('engine'),
                'engine_size': lot_data.get('engine_size'),
                'location': lot_data['location'],
                'location_old': lot_data.get('location_old'),
                'country': lot_data['country'],
                'image_thubnail': image_thumbnail,
                'is_buynow': lot_data.get('is_buynow', False),
                'link_img_hd': lot_data.get('link_img_hd', []),
                'link_img_small': lot_data.get('link_img_small', []),
                'link': lot_data['link'],
                'risk_index': risk_index,
                'is_historical': auction_date_passed,
                'vehicle_type': vehicle_type,
                'make': make,
                'model': model,
                'series': series,
                'damage_pr': damage_pr,
                'damage_sec': damage_sec,
                'keys': keys,
                'odobrand': odobrand,
                'fuel': fuel,
                'drive': drive,
                'transmission': transmission,
                'color': color,
                'status': status,
                'auction_status': auction_status,
                'body_type': body_type,
                'title': title,
                'seller_type': seller_type,
                'seller': seller,
                'document': document,
                'document_old': document_old,
                'base_site': base_site
            }

            # 6. Создаем новую запись в правильном шарде
            lot = await shard_class.create(**lot_attrs)

            # 7. Обработка завершенных аукционов
            if auction_date_passed:
                historical_shard = await HistoricalLot.get_shard_for_new_record()
                if not await HistoricalLot.filter(vin=lot_data['vin']).exists():
                    await historical_shard.create(**lot_attrs)
                
                addon_shard = await LotHistoryAddons.get_shard_for_new_record()
                addon_data = {**lot_attrs, 'updated_at': datetime.now()}
                existing_addon = await LotHistoryAddons.filter(
                    vin=lot_data['vin'], 
                    lot_id=lot_data['lot_id']
                ).first()
                
                if existing_addon:
                    await existing_addon.update_from_dict(addon_data)
                    await existing_addon.save()
                else:
                    await addon_shard.create(**addon_data)

            logger.success(f"Created lot in {shard_class.__name__} -> {lot_data['vin']}:{lot_attrs['lot_id']}")
            return lot

    except Exception as e:
        logger.error(f"Unexpected error creating lot: {str(e)}", exc_info=True)
        return None

async def update_lot_with_relations(lot_data: dict) -> Optional[LotBase]:
    """
    Создает или обновляет лот в базе данных со всеми связанными моделями.
    Если лот уже существует, обновляет его данные.
    Если vehicle_type.slug != 'automobile', добавляет/обновляет только в LotOtherVehicle.
    """
    try:
        current_date = datetime.now().date()
        auction_date_str = lot_data.get('auction_date') or lot_data.get('sale_date')
        auction_date_passed = False
        auction_date = None
        
        # Handle datetime parsing more robustly
        if auction_date_str:
            if isinstance(auction_date_str, datetime):
                auction_date = auction_date_str
            elif isinstance(auction_date_str, str):
                try:
                    # Try parsing with timezone first
                    try:
                        auction_date = datetime.strptime(auction_date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
                    except ValueError:
                        # Fallback to non-timezone format
                        auction_date = datetime.strptime(auction_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError as e:
                    logger.error(f"Error parsing date {auction_date_str}: {e}")
            else:
                logger.error(f"Unexpected auction_date type: {type(auction_date_str)}")
            
            if auction_date:
                auction_date_passed = auction_date.date() < current_date

        # Обработка изображений
        image_thumbnail = None
        if lot_data.get('link_img_small'):
            image_thumbnail = lot_data['link_img_small'][0]
        elif lot_data.get('link_img_hd'):
            image_thumbnail = lot_data['link_img_hd'][0]

        async with in_transaction():
            # 1. Проверяем наличие лота во всех таблицах
            tables_to_check = [
                Lot, LotWithoutAuctionDate, LotWithouImage,
                HistoricalLot, LotHistoryAddons, LotOtherVehicle, LotOtherVehicleHistorical
            ]
            
            existing_lot = None
            source_table = None
            
            for model in tables_to_check:
                existing = await model.filter(
                    lot_id=lot_data['lot_id'],
                    vin=lot_data['vin']
                ).first()
                if existing:
                    existing_lot = existing
                    source_table = model
                    break

            # 2. Определяем целевую таблицу для сохранения
            vin = lot_data.get('vin', '')
            
            # Получаем vehicle_type для проверки slug
            vehicle_type_name = VEHICLE_TYPE_NORMALIZER.get(
                lot_data['vehicle_type'], 
                lot_data['vehicle_type']
            )
            
            if vehicle_type_name.startswith("Snow"):
                vehicle_type_name = "Snowmobile"
            elif vehicle_type_name.startswith("Dirt") or vehicle_type_name.startswith("Bike"):
                vehicle_type_name = "Dirt Bikes"
            
            vehicle_type = await VehicleType.get_or_create_by_name(vehicle_type_name)
            
            # Определяем целевую таблицу
            if vehicle_type.slug != 'automobile':
                LotModel = LotOtherVehicle
                if auction_date_passed:
                    LotModel = LotOtherVehicleHistorical
            else:
                if len(vin) != 17:
                    LotModel = LotOtherVehicle
                else:
                    if auction_date is None:
                        LotModel = LotWithoutAuctionDate
                    elif auction_date_passed:
                        LotModel = HistoricalLot
                    else:
                        LotModel = Lot

                if image_thumbnail is None and LotModel not in {LotOtherVehicle, HistoricalLot}:
                    LotModel = LotWithouImage

            # Если лот уже существует, но в другой таблице, перемещаем его
            if existing_lot and not isinstance(existing_lot, LotModel):
                logger.info(f"Moving lot {existing_lot.id} from {source_table.__name__} to {LotModel.__name__}")
                existing_lot = await existing_lot.move_to(LotModel)
            
            # 3. Подготовка связанных моделей
            try:
                make = await Make.get_or_create_by_name(lot_data['make'], vehicle_type=vehicle_type)
                model = await Model.get_or_create_by_name(lot_data['model'], make=make)
                
                series_name = lot_data.get('series') or (lot_data.get('title') or '').split(' ')[-1]
                series = await Series.get_or_create_by_name(series_name, model=model) if series_name else None
                
                await create_model_translations("vehicle_type", vehicle_type)
            except Exception as e:
                logger.error(f"Error creating vehicle hierarchy: {str(e)}")
                return None

            # Подготовка опциональных связанных моделей
            damage_pr = await DamagePrimary.get_or_create_by_name(lot_data.get('damage_pr')) if lot_data.get('damage_pr') else None
            damage_sec = await DamageSecondary.get_or_create_by_name(lot_data.get('damage_sec')) if lot_data.get('damage_sec') else None
            keys = await Keys.get_or_create_by_name(lot_data.get('keys')) if lot_data.get('keys') else None
            odobrand = await OdoBrand.get_or_create_by_name(lot_data.get('odobrand')) if lot_data.get('odobrand') else None
            fuel = await Fuel.get_or_create_by_name(lot_data.get('fuel')) if lot_data.get('fuel') else None
            drive = await Drive.get_or_create_by_name(lot_data.get('drive')) if lot_data.get('drive') else None
            transmission = await Transmission.get_or_create_by_name(lot_data.get('transmission')) if lot_data.get('transmission') else None
            
            color_name = lot_data.get('color', 'Other')
            color = await Color.get_or_create_by_name(
                color_name if color_name in [
                    "Blue", "Grey", "Black", "Orange", "Turquoise", "Yellow", 
                    "Charcoal", "Silver", "White", "Other", "Green", "Red", 
                    "Brown", "Purple", "Gold", "Pink", "Beige", "Two Colors"
                ] else "Two Colors"
            )
            
            status_name = lot_data.get('status')
            if status_name:
                status_name = {
                    "Run & Drive": "Run & Drive",
                    "Enhanced Vehicle": "Run & Drive",
                    "Engine Start Program": "Starts",
                    "Does not Start": "Stationary"
                }.get(status_name, status_name)
                status = await Status.get_or_create_by_name(status_name)
            else:
                status = None
                
            auction_status = await AuctionStatus.get_or_create_by_name(lot_data.get('auction_status','Not sold'))
            body_type = await BodyType.get_or_create_by_name(lot_data.get('body_type')) if lot_data.get('body_type') else None
            title = await Title.get_or_create_by_name(lot_data.get('title')) if lot_data.get('title') else None
            
            seller_type_name = (lot_data.get('seller_type') or '').capitalize()
            seller_type = await SellerType.get_or_create_by_name(
                seller_type_name if seller_type_name in [
                    "Dealer", "Insurance companies", "Rental companies", 
                    "Financing", "Third parties"
                ] else "Third parties"
            )
            
            seller = await Seller.get_or_create_by_name(lot_data.get('seller')) if lot_data.get('seller') else None
            if lot_data.get('document_old'):
                document_short_type = classify_title(lot_data.get('document_old'))
            else:
                document_short_type = "Unknown"
            document = await Document.get_or_create_by_name(document_short_type)
            document_old = await DocumentOld.get_or_create_by_name(lot_data.get('document_old')) if lot_data.get('document_old') else None
            
            base_site_name = lot_data.get('base_site', '').lower()
            if base_site_name in ['iaai', 'copart']:
                if base_site_name == "iaai":
                    base_site_name = base_site_name.upper()
                else:
                    base_site_name = base_site_name.capitalize()
                base_site = await BaseSite.get_or_create_by_name(base_site_name)
            else:
                base_site = None

            # Create translations for relational models
            for rel_model, rel_instance in [
                ("damage_pr", damage_pr),
                ("document", document),
                ("damage_sec", damage_sec),
                ("keys", keys),
                ("odobrand", odobrand),
                ("fuel", fuel),
                ("drive", drive),
                ("transmission", transmission),
                ("color", color),
                ("status", status),
                ("auction_status", auction_status),
                ("body_type", body_type),
                ("seller_type", seller_type)
            ]:
                if rel_instance:
                    await create_model_translations(rel_model, rel_instance)

            # Расчет risk_index
            risk_index = await calculate_risk_index(
                year=lot_data.get('year'),
                odometer=lot_data.get('odometer'),
                auction_status=auction_status.name if auction_status else None,
                status=status.name if status else None,
                have_history=False
            )

            # 4. Подготовка данных для сохранения/обновления
            lot_attrs = {
                'odometer': lot_data.get('odometer'),
                'price': lot_data.get('price'),
                'reserve_price': lot_data.get('reserve_price'),
                'bid': lot_data.get('bid', 0),
                'auction_date': auction_date,
                'cost_repair': lot_data.get('cost_repair'),
                'year': lot_data['year'],
                'cylinders': lot_data.get('cylinders'),
                'state': lot_data['state'],
                'engine': lot_data.get('engine'),
                'engine_size': lot_data.get('engine_size'),
                'location': lot_data['location'],
                'location_old': lot_data.get('location_old'),
                'country': lot_data['country'],
                'image_thubnail': image_thumbnail,
                'is_buynow': lot_data.get('is_buynow', False),
                'link_img_hd': lot_data.get('link_img_hd', []),
                'link_img_small': lot_data.get('link_img_small', []),
                'link': lot_data['link'],
                'risk_index': risk_index,
                'is_historical': True if auction_date_passed else False,
                'vehicle_type': vehicle_type,
                'make': make,
                'model': model,
                'series': series,
                'damage_pr': damage_pr,
                'damage_sec': damage_sec,
                'keys': keys,
                'odobrand': odobrand,
                'fuel': fuel,
                'drive': drive,
                'transmission': transmission,
                'color': color,
                'status': status,
                'auction_status': auction_status,
                'body_type': body_type,
                'title': title,
                'seller_type': seller_type,
                'seller': seller,
                'document': document,
                'document_old': document_old,
                'base_site': base_site
            }

            # 5. Создаем или обновляем запись
            if existing_lot:
                # Обновляем существующий лот
                await existing_lot.update_from_dict(lot_attrs)
                await existing_lot.save()
                lot = existing_lot
                logger.info(f"Updated existing lot -> {lot_data['vin']}:{lot_data['lot_id']}")
            else:
                # Создаем новый лот
                lot_attrs['lot_id'] = lot_data['lot_id']
                lot_attrs['vin'] = lot_data['vin']
                lot = await LotModel.create(**lot_attrs)
                logger.info(f"Created new lot -> {lot_data['vin']}:{lot_data['lot_id']}")

            # 6. Обработка завершенных аукционов
            if auction_date_passed or lot_attrs['is_historical']:
                # Обновляем или создаем запись в HistoricalLot
                historical_attrs = {
                    **lot_attrs,
                    'lot_id': lot_data['lot_id'],
                    'vin': lot_data['vin']
                }
                
                historical_lot = await HistoricalLot.filter(
                    vin=lot_data['vin'],
                    lot_id=lot_data['lot_id']
                ).first()
                
                if historical_lot:
                    await historical_lot.update_from_dict(historical_attrs)
                    await historical_lot.save()
                else:
                    await HistoricalLot.create(**historical_attrs)
                
                # Обновляем или создаем запись в Addons
                addon_data = {
                    **historical_attrs,
                    'updated_at': datetime.now()
                }
                
                existing_addon = await LotHistoryAddons.filter(
                    vin=lot_data['vin'],
                    lot_id=lot_data['lot_id']
                ).first()
                
                if existing_addon:
                    await existing_addon.update_from_dict(addon_data)
                    await existing_addon.save()
                else:
                    await LotHistoryAddons.create(**addon_data)

            logger.success(f"Processed lot -> {lot_data['vin']}:{lot_data['lot_id']}")
            return lot

    except Exception as e:
        logger.error(f"Unexpected error processing lot: {str(e)}", exc_info=True)
        return None


async def find_lots_by_price_range(
    min_price: float = None, 
    max_price: float = None,
    language: Optional[str] = "en",
    offset: int = 18,
    is_historical: bool = False,
    limit: int = 5
) -> List[Lot]:
    """
    Находит лоты в указанном диапазоне цен.
    Возвращает список лотов с предзагруженными связанными данными.
    """
    query = await get_base_queryset(is_historical)
    # Применяем фильтры по цене
    if min_price is not None:
        query = query.filter(reserve_price__gte=min_price)
    if max_price is not None:
        query = query.filter(reserve_price__lte=max_price)
    
    lots = await query.offset(offset).limit(limit)
    count = await query.count()
    
    results = [await lot_to_dict(language, lot) for lot in lots]
    
    return {
        "count": count,
        "results": results,
    }


async def find_similar_lots(original_lot_id: int, limit: int = 5) -> List[Lot]:
    """
    Находит похожие лоты на основе характеристик исходного лота.
    Загружает все связанные данные для каждого лота.
    Похожие лоты берутся с того же аукциона (base_site), что и исходный лот.
    """
    if str(original_lot_id).startswith("6"):
        original_lot = await LotOtherVehicle.filter(id=original_lot_id).prefetch_related(
            "vehicle_type", "make", "model", "series", "base_site", 
            "damage_pr", "damage_sec", "keys", "odobrand", "fuel", 
            "drive", "transmission", "color", "status", "auction_status", 
            "body_type", "title", "seller_type", "seller", "document", "document_old"
        ).first()
        if not original_lot:
            raise ValueError(f"Лот с ID {original_lot_id} не найден")

        # Базовый запрос с предзагрузкой всех связей и фильтрацией по base_site
        query = LotOtherVehicle.filter(
            ~Q(id=original_lot_id),
            base_site_id=original_lot.base_site_id  # Фильтруем только лоты с того же аукциона
        ).prefetch_related(
            "vehicle_type", "make", "model", "series", "base_site", 
            "damage_pr", "damage_sec", "keys", "odobrand", "fuel", 
            "drive", "transmission", "color", "status", "auction_status", 
            "body_type", "title", "seller_type", "seller", "document", "document_old"
        )
    else:

        # Получаем исходный лот с предзагрузкой всех связанных моделей
        original_lot = await Lot1.filter(id=original_lot_id).prefetch_related(
            "vehicle_type", "make", "model", "series", "base_site", 
            "damage_pr", "damage_sec", "keys", "odobrand", "fuel", 
            "drive", "transmission", "color", "status", "auction_status", 
            "body_type", "title", "seller_type", "seller", "document", "document_old"
        ).first()
        
        if not original_lot:
            raise ValueError(f"Лот с ID {original_lot_id} не найден")

        # Базовый запрос с предзагрузкой всех связей и фильтрацией по base_site
        query = Lot1.filter(
            ~Q(id=original_lot_id),
            base_site_id=original_lot.base_site_id  # Фильтруем только лоты с того же аукциона
        ).prefetch_related(
            "vehicle_type", "make", "model", "series", "base_site", 
            "damage_pr", "damage_sec", "keys", "odobrand", "fuel", 
            "drive", "transmission", "color", "status", "auction_status", 
            "body_type", "title", "seller_type", "seller", "document", "document_old"
        )

    # Критерии схожести
    similar_criteria = [
        # 1. Совпадение марки и модели
        Q(make_id=original_lot.make_id) & Q(model_id=original_lot.model_id),
        
        # 2. Совпадение марки + близкий год выпуска
        Q(make_id=original_lot.make_id) & Q(year__gte=original_lot.year - 2) & Q(year__lte=original_lot.year + 2),
        
        # 3. Совпадение типа кузова + марка + близкая цена
        Q(body_type_id=original_lot.body_type_id) & Q(make_id=original_lot.make_id) & 
        Q(price__gte=original_lot.price * 0.7 if original_lot.price else None) & 
        Q(price__lte=original_lot.price * 1.3 if original_lot.price else None),
        
        # 4. Совпадение типа транспортного средства + год + пробег
        Q(vehicle_type_id=original_lot.vehicle_type_id) & 
        Q(year__gte=original_lot.year - 3) & Q(year__lte=original_lot.year + 3) &
        Q(odometer__gte=original_lot.odometer * 0.7 if original_lot.odometer else None) & 
        Q(odometer__lte=original_lot.odometer * 1.3 if original_lot.odometer else None),
        
        # 5. Близкие характеристики без совпадения марки
        Q(year__gte=original_lot.year - 1) & Q(year__lte=original_lot.year + 1) &
        Q(price__gte=original_lot.price * 0.8 if original_lot.price else None) & 
        Q(price__lte=original_lot.price * 1.2 if original_lot.price else None) &
        Q(odometer__gte=original_lot.odometer * 0.8 if original_lot.odometer else None) & 
        Q(odometer__lte=original_lot.odometer * 1.2 if original_lot.odometer else None)
    ]

    similar_lots = []
    for criteria in similar_criteria:
        if len(similar_lots) >= limit:
            break
            
        current_lots = await query.filter(criteria).limit(limit - len(similar_lots)).all()
        for lot in current_lots:
            if lot.id not in [l.id for l in similar_lots]:
                similar_lots.append(lot)
                if len(similar_lots) >= limit:
                    break

    # Если не набрали достаточно лотов, добавляем дополнительные с того же аукциона
    if len(similar_lots) < limit:
        remaining = limit - len(similar_lots)
        additional_lots = await query.filter(
            Q(year__gte=original_lot.year - 5) & Q(year__lte=original_lot.year + 5),
            Q(price__gte=original_lot.price * 0.5 if original_lot.price else None) & 
            Q(price__lte=original_lot.price * 1.5 if original_lot.price else None)
        ).limit(remaining).all()
        
        for lot in additional_lots:
            if lot.id not in [l.id for l in similar_lots]:
                similar_lots.append(lot)
                if len(similar_lots) >= limit:
                    break

    # Сортируем по степени схожести
    similar_lots.sort(
        key=lambda x: (
            0 if x.make_id == original_lot.make_id and x.model_id == original_lot.model_id else 1,
            abs(x.year - original_lot.year) if x.year and original_lot.year else 9999,
            abs(x.price - original_lot.price) if x.price and original_lot.price else 999999,
            abs(x.odometer - original_lot.odometer) if x.odometer and original_lot.odometer else 9999999,
        )
    )

    return similar_lots[:limit]


async def get_lots_by_ids(lot_ids: List[int]) -> List[Lot]:
    """
    Получает лоты по списку ID с предзагрузкой связей
    """
    if not lot_ids:
        return []
    
    return await Lot1.filter(id__in=lot_ids).prefetch_related(
        "vehicle_type", "make", "model", "damage_pr", "damage_sec",
        "fuel", "transmission", "color", "status", "auction_status"
    ).all()


async def get_lots_count_by_vehicle_type(
    vehicle_type_slug: str,
    include_historical: bool = False
) -> int:
    """
    Получает количество лотов по типу транспортного средства
    
    Args:
        vehicle_type_slug: Slug типа транспортного средства (например 'automobile')
        include_historical: Использовать ли таблицу HistoricalLot
        
    Returns:
        Количество лотов (int)
    """
    model = HistoricalLot if include_historical else Lot
    query = Q(vehicle_type__slug=vehicle_type_slug)
    
    return await model.filter(query).count()


async def fetch_history_data(lot_id):
    url = f"https://api.apicar.store/api/sale-histories/lot-id?lot_id={lot_id}"
    return {}
    headers = {
        'accept-language': 'en-GB,en;q=0.5',
        'api-key': 'c435aa4c-3950-43ad-82cd-7274a9ed0af1',
        'origin': 'https://admin.apicar.store',
        'priority': 'u=1, i',
        'referer': 'https://admin.apicar.store/',
        'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'sec-gpc': '1'
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # Check for HTTP errors
            return response.json()  # Return JSON response
        except httpx.HTTPStatusError as e:
            return {"error": str(e)}  # Handle HTTP errors
        except httpx.RequestError as e:
            return {"error": str(e)}  # Handle other types of errors


async def fetch_vin_data(vin):
    url = f"https://api.apicar.store/api/sale-histories/vin?vin={vin}"
    return {}
    headers = {
        'accept-language': 'en-GB,en;q=0.5',
        'api-key': 'c435aa4c-3950-43ad-82cd-7274a9ed0af1',
        'origin': 'https://admin.apicar.store',
        'priority': 'u=1, i',
        'referer': 'https://admin.apicar.store/',
        'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'sec-gpc': '1'
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # Check for HTTP errors
            return response.json()  # Return JSON response
        except httpx.HTTPStatusError as e:
            return {"error": str(e)}  # Handle HTTP errors
        except httpx.RequestError as e:
            return {"error": str(e)}  # Handle other types of errors


async def search_lots(search_info: str) -> List[Union[Lot, HistoricalLot, LotWithoutAuctionDate]]:
    search_info = search_info.strip()
    
    prefetch_make = Prefetch("make", queryset=Make.all().only("id", "name", "slug"))
    prefetch_model = Prefetch("model", queryset=Model.all().only("id", "name", "slug"))
    prefetch_series = Prefetch("series", queryset=Series.all().only("id", "name", "slug"))
    prefetch_base_site = Prefetch("base_site", queryset=BaseSite.all().only("id", "name"))
    
    base_prefetches = [
        prefetch_make,
        prefetch_model,
        prefetch_series,
        prefetch_base_site,
        "seller_type",
        "color",
        "seller"
    ]
    
    if len(search_info) == 17 and search_info.isalnum():
        query = Q(vin__iexact=search_info) & Q(vin__isnull=False) & ~Q(vin='')
    elif search_info.isdigit():
        query = Q(lot_id=int(search_info))
    else:
        search_parts = search_info.split()
        if len(search_parts) >= 2:
            make_query = Q(make__name__istartswith=search_parts[0])
            model_query = Q(model__name__istartswith=" ".join(search_parts[1:]))
            query = make_query & model_query
        else:
            query = (
                Q(make__name__iexact=search_info) |
                Q(model__name__iexact=search_info) |
                Q(make__name__istartswith=search_info) |
                Q(model__name__istartswith=search_info) |
                Q(series__name__istartswith=search_info)
            )

    # Ограничиваем количество результатов на уровне запросов
    queries = [
        Lot.filter(query).prefetch_related(*base_prefetches).limit(3),
        Lot1.filter(query).prefetch_related(*base_prefetches).limit(3),
        Lot2.filter(query).prefetch_related(*base_prefetches).limit(3),
        Lot3.filter(query).prefetch_related(*base_prefetches).limit(3),
        Lot4.filter(query).prefetch_related(*base_prefetches).limit(3),
        Lot5.filter(query).prefetch_related(*base_prefetches).limit(3),
        Lot6.filter(query).prefetch_related(*base_prefetches).limit(3),
        Lot7.filter(query).prefetch_related(*base_prefetches).limit(3),
        HistoricalLot.filter(query).prefetch_related(*base_prefetches).limit(3),
        LotWithoutAuctionDate.filter(query).prefetch_related(*base_prefetches).limit(3),
        LotWithouImage.filter(query).prefetch_related(*base_prefetches).limit(3),
        LotOtherVehicle.filter(query).prefetch_related(*base_prefetches).limit(3),
        LotOtherVehicleHistorical.filter(query).prefetch_related(*base_prefetches).limit(3),
        LotHistoryAddons.filter(query).prefetch_related(*base_prefetches).limit(3)
    ]
    
    results = await asyncio.gather(*[q for q in queries])

    seen_ids = set()
    unique_lots: List[Lot] = []

    for lots in results:
        for lot in lots:
            if lot.id not in seen_ids:
                if len(search_info) == 17 and search_info.isalnum():
                    # Если искали по VIN, проверяем точное совпадение
                    if lot.vin.lower() == search_info.lower():
                        seen_ids.add(lot.id)
                        unique_lots.append(lot)
                else:
                    if len(str(lot.id)) >= 6:
                        seen_ids.add(lot.id)
                        unique_lots.append(lot)
            if len(unique_lots) >= 15:
                break
        if len(unique_lots) >= 15:
            break

    # Предзагрузка ключевых связей
    for lot in unique_lots:
        await lot.fetch_related('make', 'model', 'series', 'base_site')
    
    unique_lots.sort(
        key=lambda x: x.auction_date if x.auction_date else datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )

    return unique_lots[:15]


async def get_base_queryset(is_historical: bool) -> Any:
    """Возвращает базовый queryset с префетчами"""
    model = HistoricalLot if is_historical else Lot
    return model.all().prefetch_related(
        "vehicle_type", "make", "model", "series",
        "status", "auction_status", "damage_pr", "damage_sec",
        "keys", "odobrand", "drive", "fuel", "body_type",
        "transmission", "base_site", "title", "seller_type",
        "seller", "document", "document_old", "color"
    )


async def get_special_filtered_lots(
    is_historical: bool,
    special_filter: List[SpecialFilterLiteral],
    limit: int,
    offset: int,
    language: str
) -> Dict[str, Any]:
    """Основная функция для получения отфильтрованных лотов"""
    queryset = await get_base_queryset(is_historical)
    
    if special_filter:
        queryset = await apply_special_filters(queryset, special_filter, is_historical)
    
    lots = await queryset.offset(offset).limit(limit)
    count = await queryset.count()
    
    results = [await lot_to_dict(language, lot) for lot in lots]
    
    return {
        "count": count,
        "results": results,
    }


async def count_all_active():
    all_count = {
        'Lot1': await Lot1.all().count(),
        'Lot2': await Lot2.all().count(),
        'Lot3': await Lot3.all().count(),
        'Lot4': await Lot4.all().count(),
        'Lot5': await Lot5.all().count(),
        'Lot6': await Lot6.all().count(),
        'Lot7': await Lot7.all().count(),
        'LotWithouImage': await LotWithouImage.all().count(),
        'LotWithoutAuctionDate': await LotWithoutAuctionDate.all().count(),
    }

    return all_count


async def count_all_auctions_active():
    models = {
        'Lot1': Lot1,
        'Lot2': Lot2,
        'Lot3': Lot3,
        'Lot4': Lot4,
        'Lot5': Lot5,
        'Lot6': Lot6,
        'Lot7': Lot7,
        'LotWithouImage': LotWithouImage,
        'LotWithoutAuctionDate': LotWithoutAuctionDate,
    }

    result = {}
    total_iaai = 0
    total_copart = 0

    for name, model in models.items():
        iaai_count = await model.filter(base_site__slug='iaai').count()
        copart_count = await model.filter(base_site__slug='copart').count()
        result[name] = {
            'iaai': iaai_count,
            'copart': copart_count
        }
        total_iaai += iaai_count
        total_copart += copart_count

    result["total"] = {
        "iaai": total_iaai,
        "copart": total_copart
    }

    return result


async def get_lot_type_by_offset_and_limit(limit: int, offset: int, cached_result: dict):
    # Распаковываем результаты из кэша
    lot_counts = cached_result.get('results', {})
    
    # Если лоты не найдены, возвращаем None
    if not lot_counts:
        return None

    # Определяем порядок обработки лотов
    lot_order = [
        'Lot1', 'Lot2', 'Lot3', 'Lot4', 'Lot5', 'Lot6', 'Lot7',
        'LotWithoutAuctionDate',
        'LotWithouImage'
    ]
    
    # Рассчитываем начальный и конечный индексы элементов
    start_idx = offset * limit
    end_idx = start_idx + limit
    
    current_position = 0
    selected_lots = []
    
    # Проходим по всем типам лотов в заданном порядке
    for lot_type in lot_order:
        count = lot_counts.get(lot_type, 0)
        if count == 0:
            continue
            
        # Определяем диапазон текущего типа лотов
        lot_start = current_position
        lot_end = current_position + count - 1
        
        # Проверяем пересечение с запрошенным диапазоном
        if start_idx <= lot_end and end_idx > lot_start:
            # Добавляем нужное количество лотов этого типа
            overlap_start = max(start_idx, lot_start)
            overlap_end = min(end_idx - 1, lot_end)
            num_lots = overlap_end - overlap_start + 1
            
            selected_lots.extend([lot_type] * num_lots)
        
        current_position += count
        
        # Если уже набрали достаточно лотов, выходим
        if len(selected_lots) >= limit:
            break
    
    # Если нашли лоты, возвращаем основной тип (первый в списке)
    if selected_lots:
        return selected_lots[0]
    
    # Если ничего не нашли, возвращаем последний доступный тип
    return 'LotWithouImage'


VALIDATOR_MODEL = {
    "Lot1": Lot1,
    "Lot2": Lot2,
    "Lot3": Lot3,
    "Lot4": Lot4,
    "Lot5": Lot5,
    "Lot6": Lot6,
    "Lot7": Lot7,
    "LotWithoutAuctionDate": LotWithoutAuctionDate,
    "LotWithouImage": LotWithouImage
}

async def get_filtered_lots(
    cache = None,
    full_url: Optional[str] = None,
    language: Optional[str] = "en",
    is_historical: Optional[bool] = False,
    base_site: Optional[List[str]] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    min_odometer: Optional[int] = None,
    max_odometer: Optional[int] = None,
    make_slug: Optional[List[str]] = None,
    model_slug: Optional[List[str]] = None,
    vehicle_type_slug: Optional[List[str]] = None,
    damage_pr_slug: Optional[List[str]] = None,
    damage_sec_slug: Optional[List[str]] = None,
    fuel_slug: Optional[List[str]] = None,
    drive_slug: Optional[List[str]] = None,
    transmission_slug: Optional[List[str]] = None,
    color_slug: Optional[List[str]] = None,
    status_slug: Optional[List[str]] = None,
    auction_status_slug: Optional[List[str]] = None,
    body_type_slug: Optional[List[str]] = None,
    series_slug: Optional[List[str]] = None,
    title_slug: Optional[List[str]] = None,
    seller_slug: Optional[List[str]] = None,
    seller_type_slug: Optional[List[str]] = None,
    document_slug: Optional[List[str]] = None,
    document_old_slug: Optional[List[str]] = None,
    cylinders: Optional[List[int]] = None,
    engine: Optional[List[str]] = None,
    engine_size: Optional[List[float]] = None,
    state: Optional[List[str]] = None,
    is_buynow: Optional[bool] = None,
    min_risk_index: Optional[float] = None,
    max_risk_index: Optional[float] = None,
    auction_date_from: Optional[datetime] = None,
    auction_date_to: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "auction_date",
    sort_order: str = "desc"
) -> Dict[str, Any]:
    auction_count = 0
    
    limit = max(1, min(limit, 100))
    sort_by = sort_by if sort_by in {
        "auction_date", "price", "year", "odometer", "created_at", "bid", "reserve_price"
    } else "auction_date"
    sort_order = sort_order.lower() if sort_order.lower() in {"asc", "desc"} else "desc"
    cached_result = None
    async with in_transaction():
        model_type = None
        key = f"all_active_count"
        logger.debug(f"KEY: {key} and Vehicle Type Slug: {vehicle_type_slug}")
        if "automobile" in vehicle_type_slug:
            if cache:
                # тут ещё логическая ошибка, но это отдельно
                if base_site and ("iaai" in base_site or "copart" in base_site) and "automobile" in vehicle_type_slug:
                    key = f"all_auction_active_count"
                cached_result = await cache.get(key)

                logger.debug(f"RESULT CACHE COUNT IN REFINED FUNCTION: {cached_result}")
                if cached_result:
                    cached_result = json.loads(cached_result)
                    model_type = await get_lot_type_by_offset_and_limit(
                        limit=limit,
                        offset=offset,
                        cached_result=cached_result,
                    )
                    logger.debug(f"model_type from cache: {model_type}")

            # безопасная проверка + дефолт
            try:
                if not model_type or model_type not in VALIDATOR_MODEL:
                    model_type = "Lot1"
                logger.debug(f"Using model_type={model_type}, cls={VALIDATOR_MODEL[model_type]}")
            except Exception as e:
                # ВАЖНО: здесь тоже возвращаем СТРОКУ, а не класс
                logger.error(f"Error with model_type {model_type}: {e}")
                model_type = "Lot1"

            if sort_by == "bid":
                model_type = "Lot6"

            if is_historical:
                query = HistoricalLot.all()
            else:
                query = VALIDATOR_MODEL[model_type].all().filter(
                    auction_date__gte=date.today()
                )
        else:
            query = LotOtherVehicleHistorical.all() if is_historical else LotOtherVehicle.all()

        exists_task = query.exists()
        # Start all filter queries concurrently
        filter_tasks = [
            apply_filters(
                query=query,
                is_historical=is_historical,
                language=language,
                base_site=base_site,
                min_year=min_year,
                max_year=max_year,
                min_odometer=min_odometer,
                max_odometer=max_odometer,
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
                body_type_slug=body_type_slug,
                series_slug=series_slug,
                title_slug=title_slug,
                seller_slug=seller_slug,
                seller_type_slug=seller_type_slug,
                document_slug=document_slug,
                document_old_slug=document_old_slug,
                engine=engine,
                engine_size=engine_size,
                state=state,
                is_buynow=is_buynow,
                min_risk_index=min_risk_index,
                max_risk_index=max_risk_index,
                auction_date_from=auction_date_from,
                auction_date_to=auction_date_to
            ),
            apply_filters(
                query=query,
                is_historical=is_historical,
                language=language,
                base_site=base_site,
                min_year=min_year,
                max_year=max_year,
                min_odometer=min_odometer,
                max_odometer=max_odometer,
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
                body_type_slug=body_type_slug,
                series_slug=series_slug,
                title_slug=title_slug,
                seller_slug=seller_slug,
                seller_type_slug=seller_type_slug,
                document_slug=document_slug,
                document_old_slug=document_old_slug,
                cylinders=cylinders,
                engine=engine,
                engine_size=engine_size,
                state=state,
                is_buynow=is_buynow,
                auction_date_from=auction_date_from,
                auction_date_to=auction_date_to
            ),
            apply_filters(
                query=query,
                is_historical=is_historical,
                language=language,
                base_site=base_site,
                min_year=min_year,
                max_year=max_year,
                min_odometer=min_odometer,
                max_odometer=max_odometer,
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
                body_type_slug=body_type_slug,
                series_slug=series_slug,
                title_slug=title_slug,
                seller_slug=seller_slug,
                seller_type_slug=seller_type_slug,
                document_slug=document_slug,
                document_old_slug=document_old_slug,
                cylinders=cylinders,
                state=state,
                is_buynow=is_buynow,
                min_risk_index=min_risk_index,
                max_risk_index=max_risk_index,
                auction_date_from=auction_date_from,
                auction_date_to=auction_date_to
            ),
            apply_filters(
                query=query,
                is_historical=is_historical,
                language=language,
                base_site=base_site,
                min_odometer=min_odometer,
                max_odometer=max_odometer,
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
                body_type_slug=body_type_slug,
                series_slug=series_slug,
                title_slug=title_slug,
                seller_slug=seller_slug,
                seller_type_slug=seller_type_slug,
                document_slug=document_slug,
                document_old_slug=document_old_slug,
                cylinders=cylinders,
                engine=engine,
                engine_size=engine_size,
                state=state,
                is_buynow=is_buynow,
                min_risk_index=min_risk_index,
                max_risk_index=max_risk_index,
                auction_date_from=auction_date_from,
                auction_date_to=auction_date_to
            )
        ]
        logger.debug('Filtered applies')
        # Wait for all filter tasks and exists check
        exists, *filtered_queries = await asyncio.gather(exists_task, *filter_tasks)
        query_to_cylinders, query_to_risk_index, query_to_engine_size, query_to_year = filtered_queries

        if not exists:
            if "automobile" not in vehicle_type_slug:
                query = LotOtherVehicleHistorical.all() if is_historical else LotOtherVehicle.all()
        if is_historical:
            auction_date_filter = None
        else:
            auction_date_filter = auction_date_from or date.today()
        # Apply main filters
        filters = {k: v for k, v in {
            "year__gte": min_year,
            "year__lte": max_year,
            "odometer__gte": min_odometer,
            "vehicle_type__slug__in": vehicle_type_slug,
            "model__slug__in": model_slug,
            "base_site__slug__in": base_site,
            "fuel__slug__in": fuel_slug,
            "damage_pr__slug__in": damage_pr_slug,
            "damage_sec__slug__in": damage_sec_slug,
            "seller__slug__in": seller_slug,
            "drive__slug__in": drive_slug,
            "status__slug__in": status_slug,
            "auction_status__slug__in": auction_status_slug,
            "seller_type__slug__in": seller_type_slug,
            "body_type__slug__in": body_type_slug,
            "document__slug__in": document_slug,
            "document_old__slug__in": document_old_slug,
            "transmission__slug__in": transmission_slug,
            "color__slug__in": color_slug,
            "make__slug__in": make_slug,
            "series__slug__in": series_slug,
            "odometer__lte": max_odometer,
            "cylinders": cylinders,
            "engine": engine,
            "engine_size": engine_size,
            "state": state,
            "is_buynow": is_buynow,
            "risk_index__gte": min_risk_index,
            "risk_index__lte": max_risk_index,
            "auction_date__gte": auction_date_filter,
            "auction_date__lte": auction_date_to,
            "is_historical": is_historical
        }.items() if v is not None}
        if "automobile" in vehicle_type_slug:
            min_od, max_od = await Lot.get_min_max_odometer_across_shards(**filters) if not is_historical else await HistoricalLot.historical_get_min_max_odometer(**filters)
            results_lots = await Lot.query_across_shards_with_limit_offset(limit=limit, offset=offset, **filters) if not is_historical else await HistoricalLot.historical_query_with_limit_offset(limit=limit, offset=offset, **filters)
            results_lots = [await lot_to_dict(language, lot) for lot in results_lots]
        else:
            min_od, max_od = await LotOtherVehicle.other_vehicle_get_min_max_odometer(**filters) if not is_historical else await LotOtherVehicleHistorical.historical_other_vehicle_get_min_max_odometer(**filters)
            results_lots = await LotOtherVehicle.other_vehicle_query_with_limit_offset(limit=limit, offset=offset, **filters) if not is_historical else await LotOtherVehicleHistorical.historical_other_vehicle_query_with_limit_offset(limit=limit, offset=offset, **filters)
            results_lots = [await lot_to_dict(language, lot) for lot in results_lots]

        query = await apply_filters(
            query=query,
            is_historical=is_historical,
            language=language,
            base_site=base_site,
            min_year=min_year,
            max_year=max_year,
            min_odometer=min_odometer,
            max_odometer=max_odometer,
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
            body_type_slug=body_type_slug,
            series_slug=series_slug,
            title_slug=title_slug,
            seller_slug=seller_slug,
            seller_type_slug=seller_type_slug,
            document_slug=document_slug,
            document_old_slug=document_old_slug,
            cylinders=cylinders,
            engine=engine,
            engine_size=engine_size,
            state=state,
            is_buynow=is_buynow,
            min_risk_index=min_risk_index,
            max_risk_index=max_risk_index,
            auction_date_from=auction_date_from,
            auction_date_to=auction_date_to
        )

        has_results = await query.exists()
        if not has_results:
            if cache:
                cached_result = await cache.get(f"{settings.CACHE_KEY}{offset}{language}{'history' if is_historical else 'active'}")
                if cached_result:
                    try:
                        result_dict = json.loads(cached_result)
                        return result_dict
                    except Exception as e:
                        logger.error(f"Error decoding cached result: {e}")

        order_by = f"-{sort_by}" if sort_order == "desc" else sort_by
        query = query.order_by(order_by)

        # Prepare all async tasks
        vehicle_type_ids_task = VehicleType.filter(slug__in=vehicle_type_slug).values_list("id", flat=True) if vehicle_type_slug else asyncio.sleep(0)
        make_ids_task = Make.filter(slug__in=make_slug).values_list("id", flat=True) if make_slug else asyncio.sleep(0)
        
        # Gather core tasks
        vehicle_type_ids, make_ids = await asyncio.gather(vehicle_type_ids_task, make_ids_task)
        
        stats_task = get_filter_stats(language, query, vehicle_type_ids)
        series_model_stats_task = get_model_series_stats(query, make_ids) if make_slug else asyncio.sleep(0)
        
        stats, series_model_stats = await asyncio.gather(
            stats_task,
            series_model_stats_task
        )

        # Process translations for vehicle types
        auto_stat = await get_relation_stats(query if await check_filter_exists(query, "vehicle_type") else query.model.all(), "vehicle_type")
        for vehicle_type in auto_stat:
            translated_value = await get_translation(
                field_name="vehicle_type", 
                original_value=vehicle_type['slug'], 
                language=language
                )
            if translated_value:
                vehicle_type['name'] = translated_value

        if series_model_stats:
            stats.update(series_model_stats)

        # Список всех моделей и их ключей
        models = {
            "color": Color,
            "body_type": BodyType,
            "fuel": Fuel,
            "transmission": Transmission,
            "seller_type": SellerType,
            "document": Document,
            "status": Status,
            "auction_status": AuctionStatus,
            "damage_pr": DamagePrimary,
            "damage_sec": DamageSecondary,
            "drive": Drive,
            "base_site": BaseSite
        }

        # Параллельная выборка всех данных
        fetched_data = await asyncio.gather(*(model.all() for model in models.values()))
        add_stats = {
            key: [dict(obj) for obj in data] for key, data in zip(models.keys(), fetched_data)
        }

        # Собираем все переводы в кучу
        translation_tasks = []
        slug_map = []

        for rel, data in add_stats.items():
            for item in data:
                slug = item["slug"]
                translation_tasks.append(get_translation(field_name=rel, original_value=slug, language=language))
                slug_map.append((rel, item))

        # Получаем переводы параллельно
        translations = await asyncio.gather(*translation_tasks)

        # Обновляем имена
        for (rel, item), translated_value in zip(slug_map, translations):
            if translated_value:
                item["name"] = translated_value

        # Обновляем финальный словарь
        stats.update(add_stats)
        
        # Run all basic stats in parallel
        basic_stats = await asyncio.gather(
            get_flat_stats(query_to_year, "year"),
            get_range_stats(query_to_risk_index, "risk_index", 25),
            get_flat_stats(query_to_engine_size, "engine_size"),
            get_flat_stats(query_to_cylinders, "cylinders"),
        )
        stats.update({
            "year": basic_stats[0],
            "risk_index": basic_stats[1],
            "engine_size": basic_stats[2],
            "cylinders": basic_stats[3],
        })

    # Final vehicle type stats
    # query = HistoricalLot.all() if is_historical else VALIDATOR_MODEL[f'{model_type}'].all() if model_type else Lot1.all()
    vehicle_types = await VehicleType.all()
    auto_stat = []
    
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

        auto_stat.append(item)
    
    # Сортируем по убыванию количества
    auto_stat.sort(key=lambda x: x['counter'], reverse=True)
            
    stats["vehicle_type"] = auto_stat
    
    # Filter out unknown values
    stats["drive"] = [drive for drive in stats["drive"] if drive["slug"] != "unknown"]
    stats["status"] = [drive for drive in stats["status"] if drive["slug"] != "unknown"]
    stats["transmission"] = [drive for drive in stats["transmission"] if drive["slug"] != "unknown"]
    stats["fuel"] = [drive for drive in stats["fuel"] if drive["slug"] != "unknown"]
    stats["document"] = [drive for drive in stats["document"] if drive["slug"] != "unknown"]
    stats["vehicle_type"] = [drive for drive in stats["vehicle_type"] if drive["slug"] != "unknown"]
    stats['odometer'] = {
            "min_val": min_od,
            "max_val": max_od
        }
    # Filter body types based on vehicle type
    vehicle_types = {
        "automobile": ["sedan", "coupe", "pickup", "suv", "cabrio", "hatchback", "limousine", "cabrio", "wagon", "van", "roadster", "liftback", "hearse"],
        "motorcycle": ["bike", "sport_bike", "roadster_bike", "enduro_bike"],
        "bus": ["bus"],
        "atv": [],
        "watercraft": [],
        "jet_sky": [],
        "boat": [],
        "trailers": ["furgon"],
        "mobile_home": [],
        "emergency_equipment": ["fire_truck"],
        "industrial_equipment": ["industrial"],
        "truck": ["truck"],
        "other": ["other"]
    }
    if vehicle_type_slug and vehicle_type_slug[0] in vehicle_types:
        vt_list = vehicle_types[vehicle_type_slug[0]]
        stats["body_type"] = [vt for vt in stats["body_type"] if vt["slug"] in vt_list]
    result = {
        "lots": results_lots,
        "count": count,
        "stats": stats
    }
    key = f"{full_url}"
    if cache:
        await cache.set(key, json.dumps(result), ttl=settings.CACHE_TTL + 180)
    return result


async def apply_filters(
    query,
    is_historical: Optional[bool] = False,
    language: Optional[str] = "en",
    # Основные фильтры
    base_site: Optional[List[str]] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    min_odometer: Optional[int] = None,
    max_odometer: Optional[int] = None,
    
    # Фильтры по связанным моделям
    make_slug: Optional[List[str]] = None,
    model_slug: Optional[List[str]] = None,
    vehicle_type_slug: Optional[List[str]] = None,
    damage_pr_slug: Optional[List[str]] = None,
    damage_sec_slug: Optional[List[str]] = None,
    fuel_slug: Optional[List[str]] = None,
    drive_slug: Optional[List[str]] = None,
    transmission_slug: Optional[List[str]] = None,
    color_slug: Optional[List[str]] = None,
    status_slug: Optional[List[str]] = None,
    body_type_slug: Optional[List[str]] = None,
    series_slug: Optional[List[str]] = None,
    title_slug: Optional[List[str]] = None,
    seller_slug: Optional[List[str]] = None,
    seller_type_slug: Optional[List[str]] = None,
    document_slug: Optional[List[str]] = None,
    document_old_slug: Optional[List[str]] = None,
    cylinders: Optional[List[int]] = None,
    engine: Optional[List[str]] = None,
    engine_size: Optional[List[float]] = None,
    # Дополнительные фильтры
    state: Optional[List[str]] = None,
    is_buynow: Optional[bool] = None,
    min_risk_index: Optional[float] = None,
    max_risk_index: Optional[float] = None,
    auction_date_from: Optional[datetime] = None,
    auction_date_to: Optional[datetime] = None,
):
    """Применяет все фильтры к запросу с поддержкой списков значений и пакетной обработкой"""
    
    # Числовые фильтры (не требуют пакетной обработки)
    if min_year is not None:
        query = query.filter(year__gte=min_year)
    if max_year is not None:
        query = query.filter(year__lte=max_year)
    if min_odometer is not None:
        query = query.filter(odometer__gte=min_odometer)
    if max_odometer is not None:
        query = query.filter(odometer__lte=max_odometer)
    if min_risk_index is not None:
        query = query.filter(risk_index__gte=min_risk_index)
    if max_risk_index is not None:
        query = query.filter(risk_index__lte=max_risk_index)

    # Фильтры по связанным моделям с пакетной обработкой
    relation_filters = {
        "vehicle_type": vehicle_type_slug,
        "damage_pr": damage_pr_slug,
        "damage_sec": damage_sec_slug,
        "fuel": fuel_slug,
        "drive": drive_slug,
        "transmission": transmission_slug,
        "color": color_slug,
        "status": status_slug,
        "body_type": body_type_slug,
        "title": title_slug,
        "seller": seller_slug,
        "seller_type": seller_type_slug,
        "document": document_slug,
        "document_old": document_old_slug,
        "base_site": base_site
    }

    for field, value in relation_filters.items():
        if value:
            filter_value = value if isinstance(value, list) else [value]
            # Применяем фильтр пакетами по 10000 элементов
            batch_size = 10000
            combined_query = Q()
            
            for i in range(0, len(filter_value), batch_size):
                batch = filter_value[i:i + batch_size]
                combined_query |= Q(**{f"{field}__slug__in": batch})
            
            query = query.filter(combined_query)

    # Фильтры по простым полям с пакетной обработкой
    simple_filters = {
        "engine_size": engine_size,
        "engine": engine,
        "cylinders": cylinders,
        "state": state,
    }

    for field, value in simple_filters.items():
        if value:
            filter_value = value if isinstance(value, list) else [value]
            batch_size = 10000
            combined_query = Q()
            
            for i in range(0, len(filter_value), batch_size):
                batch = filter_value[i:i + batch_size]
                combined_query |= Q(**{f"{field}__in": batch})
            
            query = query.filter(combined_query)

    # Фильтрация по марке с пакетной обработкой
    if make_slug:
        make_filter = make_slug if isinstance(make_slug, list) else [make_slug]
        batch_size = 10000
        combined_query = Q()
        
        for i in range(0, len(make_filter), batch_size):
            batch = make_filter[i:i + batch_size]
            combined_query |= Q(make__slug__in=batch)
        
        query = query.filter(combined_query)

    # Фильтрация по модели с проверкой соответствия марке и пакетной обработкой
    if model_slug:
        model_filter = model_slug if isinstance(model_slug, list) else [model_slug]
        
        if make_slug:
            # Получаем ID моделей, которые принадлежат указанным маркам (пакетами)
            batch_size = 10000
            valid_models = []
            make_filter = make_slug if isinstance(make_slug, list) else [make_slug]
            
            # Обрабатываем модели пакетами
            for i in range(0, len(model_filter), batch_size):
                model_batch = model_filter[i:i + batch_size]
                
                # Обрабатываем марки пакетами
                for j in range(0, len(make_filter), batch_size):
                    make_batch = make_filter[j:j + batch_size]
                    
                    batch_models = await Model.filter(
                        slug__in=model_batch,
                        make__slug__in=make_batch
                    ).values_list('id', flat=True)
                    valid_models.extend(batch_models)
            
            if valid_models:
                # Применяем фильтр по ID моделей пакетами
                model_batch_size = 10000
                combined_query = Q()
                
                for i in range(0, len(valid_models), model_batch_size):
                    batch = valid_models[i:i + model_batch_size]
                    combined_query |= Q(model_id__in=batch)
                
                query = query.filter(combined_query)
            else:
                return query.filter(id__isnull=True)
        else:
            # Простая фильтрация по моделям пакетами
            batch_size = 10000
            combined_query = Q()
            
            for i in range(0, len(model_filter), batch_size):
                batch = model_filter[i:i + batch_size]
                combined_query |= Q(model__slug__in=batch)
            
            query = query.filter(combined_query)

    # Фильтрация по серии с проверкой соответствия модели и пакетной обработкой
    if series_slug:
        series_filter = series_slug if isinstance(series_slug, list) else [series_slug]
        batch_size = 10000
        valid_series_ids = []
        
        # Обрабатываем серии пакетами
        for i in range(0, len(series_filter), batch_size):
            series_batch = series_filter[i:i + batch_size]
            series_query = Series.filter(slug__in=series_batch)
            
            # Если указана модель, фильтруем серии по модели (также пакетами)
            if model_slug:
                model_filter = model_slug if isinstance(model_slug, list) else [model_slug]
                
                # Обрабатываем модели пакетами
                for j in range(0, len(model_filter), batch_size):
                    model_batch = model_filter[j:j + batch_size]
                    series_query = series_query.filter(model__slug__in=model_batch)
            
            batch_series_ids = await series_query.values_list('id', flat=True)
            valid_series_ids.extend(batch_series_ids)
        
        if valid_series_ids:
            # Применяем фильтр по ID серий пакетами
            series_batch_size = 10000
            combined_query = Q()
            
            for i in range(0, len(valid_series_ids), series_batch_size):
                batch = valid_series_ids[i:i + series_batch_size]
                combined_query |= Q(series_id__in=batch)
            
            query = query.filter(combined_query)
        else:
            return query.filter(id__isnull=True)

    # Дополнительные фильтры (не требуют пакетной обработки)
    if is_buynow is not None:
        query = query.filter(is_buynow=is_buynow)
    
    if auction_date_from is not None:
        query = query.filter(auction_date__gte=auction_date_from)
    if auction_date_to is not None:
        query = query.filter(auction_date__lte=auction_date_to)
    
    return query


async def get_lots_with_pagination(language, query, offset: int, limit: int) -> List[Dict]:
    """Получает список лотов с пагинацией и преобразует в словари"""
    lot_objects = await query.offset(offset).limit(limit).prefetch_related(
        "make", "model", "vehicle_type", "damage_pr", "damage_sec",
        "fuel", "drive", "transmission", "color", "status", "body_type",
        "series", "base_site", "seller", "seller_type", "document", "document_old", "title"
    )
    
    return [await lot_to_dict(language, lot) for lot in lot_objects]


async def lot_to_dict(language, lot) -> Dict:
    """Преобразует объект Lot в словарь"""
    result = {
        "id": lot.id,
        "lot_id": lot.lot_id,
        "odometer": lot.odometer,
        "price": lot.price,
        "reserve_price": lot.reserve_price,
        "bid": lot.bid,
        "auction_date": lot.auction_date.isoformat() if lot.auction_date else None,
        "cost_repair": lot.cost_repair,
        "year": lot.year,
        "cylinders": lot.cylinders,
        "vin": lot.vin,
        "engine": lot.engine,
        "engine_size": lot.engine_size,
        "location": lot.location,
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
    
    # Добавляем связанные поля
    related_fields = [
        "make", "model", "vehicle_type", "damage_pr", "damage_sec",
        "fuel", "drive", "transmission", "color", "status", "body_type",
        "series", "base_site", "seller", "seller_type", "document", "document_old", "title"
    ]
    
    for field in related_fields:
        related_obj = getattr(lot, field)
        if related_obj:
            translated_value = await get_translation(
                field_name=field, 
                original_value=related_obj.slug, 
                language=language
                )
            if translated_value:
                result[f"{field}_name"] = translated_value
            else:
                result[f"{field}_name"] = related_obj.name
            result[f"{field}_slug"] = related_obj.slug
            if field == "color" and hasattr(related_obj, 'hex'):
                result["hex"] = related_obj.hex
            if field == "status" and hasattr(related_obj, 'hex'):
                result["hex"] = related_obj.hex
                result["letter"] = related_obj.letter
                result["description"] = related_obj.description
            if field == "make" and hasattr(related_obj, 'icon_path'):
                result["icon_path"] = related_obj.icon_path
                result["popular_counter"] = related_obj.popular_counter
        else:
            result[f"{field}_name"] = None
            result[f"{field}_slug"] = None
    return result


async def get_all_lot_ids(query) -> List[Dict[str, int]]:
    """Получает только id лотов (без prefetch и to_dict)"""
    return await query.only("id").values("id")


async def get_additional_filter_stats(query, applied_filters=None):
    """
    Получает расширенную статистику по лотам, исключая фильтрацию по самим анализируемым полям,
    но учитывая все остальные фильтры.
    
    Args:
        query: Базовый QuerySet с примененными фильтрами
        applied_filters: Словарь с примененными фильтрами
        
    Returns:
        Словарь с статистикой по всем важным полям
    """
    if applied_filters is None:
        applied_filters = {}

    stats = {}
    
    # Поля, для которых нужно показать все варианты (исключая их собственную фильтрацию)
    stat_fields = [
        "body_type", "color", "fuel", "transmission",
        "seller_type", "document", "status", "auction_status",
        "damage_pr", "damage_sec", "drive", "base_site"
    ]
    
    # 1. Создаем новый запрос, сохраняя все фильтры кроме относящихся к stat_fields
    model = query.model
    stats_query = model.all()
    # Маппинг названий фильтров на поля запроса
    FILTER_MAPPING = {
        'make_slug': 'make__slug__in',
        'model_slug': 'model__slug__in',
        'vehicle_type_slug': 'vehicle_type__slug__in',
        'damage_pr_slug': 'damage_pr__slug__in',
        'damage_sec_slug': 'damage_sec__slug__in',
        'fuel_slug': 'fuel__slug__in',
        'drive_slug': 'drive__slug__in',
        'transmission_slug': 'transmission__slug__in',
        'color_slug': 'color__slug__in',
        'status_slug': 'status__slug__in',
        'body_type_slug': 'body_type__slug__in',
        'series_slug': 'series__slug__in',
        'title_slug': 'title__slug__in',
        'seller_slug': 'seller__slug__in',
        'seller_type_slug': 'seller_type__slug__in',
        'document_slug': 'document__slug__in',
        'document_old_slug': 'document_old__slug__in',
        'base_site': 'base_site__in',
        'state': 'state__in',
        'cylinders': 'cylinders__in',
        'engine': 'engine__in',
        'engine_size': 'engine_size__in'
    }
    
    # 2. Применяем фильтры из query._filter_kwargs
    if hasattr(query, '_filter_kwargs'):
        for key, value in query._filter_kwargs.items():
            field = key.split('__')[0]  # Извлекаем базовое имя поля
            if field not in stat_fields:
                stats_query = stats_query.filter(**{key: value})
    
    # 3. Применяем фильтры из applied_filters
    for filter_key, filter_value in applied_filters.items():
        if filter_value is None:
            continue
            
        # Пропускаем фильтры по stat_fields
        field = filter_key.replace('_slug', '')
        if field in stat_fields:
            continue
            
        # Получаем правильное имя поля для фильтрации
        filter_field = FILTER_MAPPING.get(filter_key, f"{filter_key}__in")
        
        # Применяем фильтр с учетом типа значения
        if isinstance(filter_value, (list, tuple)):
            stats_query = stats_query.filter(**{filter_field: filter_value})
        else:
            stats_query = stats_query.filter(**{filter_field: [filter_value]})
    
    # 4. Применяем числовые фильтры и фильтры по датам
    numeric_filters = {
        'year': ('year__gte', 'year__lte'),
        'odometer': ('odometer__gte', 'odometer__lte'),
        'risk_index': ('risk_index__gte', 'risk_index__lte')
    }
    
    for field, (min_key, max_key) in numeric_filters.items():
        if min_key in applied_filters:
            stats_query = stats_query.filter(**{min_key: applied_filters[min_key]})
        if max_key in applied_filters:
            stats_query = stats_query.filter(**{max_key: applied_filters[max_key]})
    
    if 'auction_date_from' in applied_filters:
        stats_query = stats_query.filter(auction_date__gte=applied_filters['auction_date_from'])
    if 'auction_date_to' in applied_filters:
        stats_query = stats_query.filter(auction_date__lte=applied_filters['auction_date_to'])
    
    if 'is_buynow' in applied_filters:
        stats_query = stats_query.filter(is_buynow=applied_filters['is_buynow'])
    # 5. Получаем статистику по всем stat_fields
    try:
        field_stats = await asyncio.gather(
            *[get_relation_stats(stats_query, field) for field in stat_fields]
        )
    except Exception as e:
        logger.error(f"Error gathering field stats: {str(e)}")
        field_stats = [[] for _ in stat_fields]
    
    # 6. Базовые статистики считаем по исходному запросу
    try:
        basic_stats = await asyncio.gather(
            get_flat_stats(query, "year"),
            get_odometer_min_max(query),
            get_range_stats(query, "risk_index", 25),
            get_flat_stats(query, "engine_size"),
            get_flat_stats(query, "cylinders"),
        )
    except Exception as e:
        logger.error(f"Error gathering basic stats: {str(e)}")
        basic_stats = [{}, {}, {}, {}, {}]
    
    # 7. Формируем итоговый результат
    stats.update({
        "year": basic_stats[0],
        "odometer": basic_stats[1],
        "risk_index": basic_stats[2],
        "engine_size": basic_stats[3],
        "cylinders": basic_stats[4],
        **dict(zip(stat_fields, field_stats))
    })
    return stats


async def get_model_series_stats(query, make_ids):
    try:
        stats = {}
        lot_ids = await query.values_list("id", flat=True)
        
        # Получаем все модели для выбранных марок
        models = await Model.filter(make_id__in=make_ids).all()
        model_ids = [m.id for m in models]
        
        # Получаем все серии для выбранных моделей
        series = await Series.filter(model_id__in=model_ids).all()
        series_ids = [s.id for s in series]

        model_stats, series_stats = await asyncio.gather(
            get_relation_stats_for_entities("model", model_ids, models, lot_ids),
            get_relation_stats_for_entities("series", series_ids, series, lot_ids),
        )
        
        stats.update({
            "model": model_stats,
            "series": series_stats
        })
        return stats
    except Exception as e:
        logger.error(f'Error in getting stats to models and series {e}')


async def get_make_stats(query, vehicle_type_ids):
    try:
        lot_ids = await query.values_list("id", flat=True)
        
        # Получаем все модели для выбранных марок
        makes = await Make.filter(vehicle_type_id__in=vehicle_type_ids).all()
        make_ids = [m.id for m in makes]

        make_stats = await get_relation_stats_for_entities("make", make_ids, makes, lot_ids)
        
        return make_stats
    except Exception as e:
        logger.error(f'Error in getting stats to models and series {e}')


async def get_relation_stats_for_entities(entity_type: str, entity_ids: List[int], entities: List[Any], lot_ids: List[int]) -> List[Dict[str, Any]]:
    try:
        if not entities:
            return []

        # Получаем статистику по лотам
        stats = await get_entity_stats_from_lots(entity_type, entity_ids, lot_ids)
        
        # Собираем полную информацию
        result = []
        for entity in entities:
            entity_data = {
                "id": entity.id,
                "name": entity.name,
                "slug": entity.slug,
                "counter": stats.get(entity.id, 0)
            }
            # Добавляем дополнительные поля, если они есть
            for field in ['hex', 'description', 'letter', 'popular_counter', 'icon_path']:
                if hasattr(entity, field):
                    entity_data[field] = getattr(entity, field)
            
            result.append(entity_data)
        
        # Сортируем по количеству (по убыванию)
        return sorted(result, key=lambda x: x['counter'], reverse=True)

    except Exception as e:
        logger.error(f"Error processing {entity_type} stats: {str(e)}", exc_info=True)
        return []

async def get_entity_stats_from_lots(entity_type: str, entity_ids: List[int], lot_ids: List[int]) -> Dict[int, int]:
    try:
        if not entity_ids or not lot_ids:
            return {}

        table_name = "lot"  # предполагаем, что таблица называется lot
        related_field = f"{entity_type}_id"

        lot_ids_str = ", ".join(map(str, lot_ids))
        entity_ids_str = ", ".join(map(str, entity_ids))

        sql = f"""
        SELECT 
            {related_field} as entity_id, 
            COUNT(id) as counter
        FROM 
            {table_name}
        WHERE 
            id IN ({lot_ids_str}) 
            AND {related_field} IN ({entity_ids_str})
            AND {related_field} IS NOT NULL
        GROUP BY 
            {related_field}
        """

        conn = Tortoise.get_connection("default")
        results = await conn.execute_query_dict(sql)
        
        return {row['entity_id']: row['counter'] for row in results}

    except Exception as e:
        logger.error(f"Error getting {entity_type} stats from lots: {str(e)}", exc_info=True)
        return {}

async def get_filter_stats(language, query, vehicle_type_ids) -> Dict[str, Any]:
    """Optimized statistics with safe batch processing for large datasets"""
    try:
        stats = {}
        try:
            async with asyncio.timeout(180):
                model = query.model

                # 1. Получаем статистики vehicle_type и make
                make_stats = await get_make_stats(query, vehicle_type_ids)
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
                stats.update({
                    "vehicle_type": result,
                    "make": make_stats
                })
                
        except asyncio.TimeoutError:
            logger.warning("Timeout while getting stats, returning partial results")
        return stats
    except Exception as e:
        logger.error(f"Error in get_filter_stats: {str(e)}", exc_info=True)
        return {}
    

async def check_filter_exists(query, field: str, applied_filters: Dict = None) -> bool:
    """Точная проверка применённых фильтров через анализ параметров запроса"""
    if applied_filters is None:
        applied_filters = {}

    # 1. Проверяем явно переданные фильтры
    if f"{field}_slug" in applied_filters or field in applied_filters:
        return True

    # 2. Анализируем параметры запроса (новый подход)
    try:
        # Получаем все параметры фильтрации из запроса
        filter_params = getattr(query, '_filter_kwargs', {})
        
        # Проверяем все возможные варианты именования поля
        field_variants = [
            field,
            f"{field}_id",
            f"{field}__slug",
            f"{field}__slug__in"
        ]
        
        # Проверяем, есть ли поле в параметрах фильтрации
        return any(fv in filter_params for fv in field_variants)
        
    except Exception as e:
        logger.error(f"Error in check_filter_exists for {field}: {str(e)}")
        return False


async def get_flat_stats(query, field: str) -> Dict[str, int]:
    """Статистика по плоским полям с пакетной обработкой"""
    try:
        batch_size = 10000
        stats = {}
        offset = 0
        
        while True:
            batch = await query.offset(offset).limit(batch_size).values_list(field, flat=True)
            if not batch:
                break
                
            for value in batch:
                if value is not None:
                    stats[str(value)] = stats.get(str(value), 0) + 1
            
            offset += batch_size
        
        return stats
    except Exception as e:
        logger.error(f"Error in get_flat_stats for {field}: {str(e)}")
        return {}


async def get_relation_stats(query, relation: str) -> List[Dict[str, Any]]:
    """Optimized relation stats with dynamic extra field support."""
    try:
        model = query.model
        field = model._meta.fields_map.get(relation)
        
        if not field:
            logger.warning(f"Relation {relation} not found in model {model.__name__}")
            return []

        related_model = getattr(field, 'related_model', getattr(field, 'model_class', None))
        if not related_model:
            logger.warning(f"No related model for {relation} in {model.__name__}")
            return []

        # Base fields that are always expected
        base_fields = ['id', 'name', 'slug']
        optional_fields = ['hex', 'description', 'letter', 'popular_counter', 'icon_path', 'icon_disable', 'icon_active']

        # Determine which optional fields are present in the related model
        all_fields = related_model._meta.fields
        selected_fields = base_fields + [f for f in optional_fields if f in all_fields]

        select_clause = ", ".join([f"r.{f}" for f in selected_fields] + ["COUNT(l.id) as counter"])
        group_by_clause = ", ".join([f"r.{f}" for f in selected_fields])

        # Table names and join field
        table_name = model._meta.db_table
        related_table = related_model._meta.db_table
        related_field = f"{relation}_id"

        sql = f"""
        WITH filtered_lots AS (
            SELECT id, {related_field}
            FROM {table_name}
            WHERE {related_field} IS NOT NULL
        )
        SELECT 
            {select_clause}
        FROM 
            filtered_lots l
        JOIN 
            {related_table} r ON l.{related_field} = r.id
        GROUP BY 
            {group_by_clause}
        ORDER BY 
            counter DESC
        """

        conn = Tortoise.get_connection("default")
        results = await conn.execute_query_dict(sql)

        return [
            {field: row[field] for field in selected_fields if field in row} | {"counter": row["counter"]}
            for row in results
        ]

    except Exception as e:
        logger.error(f"Error processing {relation} stats: {str(e)}", exc_info=True)
        return []


async def get_odometer_min_max(query) -> Dict[str, float]:
    """Retrieve the min and max odometer values"""
    try:
        # First get the filtered IDs
        ids = await query.values_list('id', flat=True)
        if not ids:
            return {}

        # Use parameterized query to get min and max odometer values
        sql = """
        SELECT 
            MIN(odometer) as min_val,
            MAX(odometer) as max_val
        FROM lot  -- Correctly reference the table name
        WHERE id = ANY($1::bigint[])
        """
        
        conn = Tortoise.get_connection("default")
        result = await conn.execute_query(sql, [list(ids)])
        
        if not result or not result[1] or result[1][0]['min_val'] is None:
            return {}

        min_val = result[1][0]['min_val']
        max_val = result[1][0]['max_val']
        
        return {
            "min_val": min_val,
            "max_val": max_val
        }
    except Exception as e:
        logger.error(f"Error in get_odometer_min_max: {str(e)}")
        return {}


async def get_range_stats(query, field: str, step: Union[int, float] = None) -> Dict[str, int]:
    """Статистика по risk_index с группировкой в 3 категории"""
    
    try:
        # Если поле не risk_index, используем старую логику
        if field != "risk_index":
            return await get_default_range_stats(query, field, step or 25)
            
        # Получаем количество в каждой категории
        low_count = await query.filter(risk_index__lt=50).count()
        medium_count = await query.filter(risk_index__gte=50, risk_index__lt=75).count()
        high_count = await query.filter(risk_index__gte=75).count()
        
        return {
            "low": low_count,
            "medium": medium_count,
            "high": high_count
        }
        
    except Exception as e:
        logger.error(f"Error in get_range_stats for {field}: {str(e)}")
        return {}

async def get_default_range_stats(query, field: str, step: Union[int, float]) -> Dict[str, int]:
    """Оригинальная логика для других полей"""
    try:
        # Получаем min и max значения
        min_max = await query.annotate(
            min_val=functions.Min(field),
            max_val=functions.Max(field)
        ).first()
        
        if not min_max or min_max.min_val is None:
            return {}

        min_val = min_max.min_val
        max_val = min_max.max_val
        
        # Оптимизируем шаг если диапазон слишком большой
        if (max_val - min_val) / step > 100:
            step = (max_val - min_val) / 20
            
        counts = {}
        current = min_val
        
        while current <= max_val:
            next_val = current + step
            count = await query.filter(
                **{f"{field}__gte": current, f"{field}__lt": next_val}
            ).count()
            if count > 0:
                counts[f"{current:.2f}-{next_val:.2f}"] = count
            current = next_val

        return counts
    except Exception as e:
        logger.error(f"Error in get_default_range_stats for {field}: {str(e)}")
        return {}


def empty_response() -> Dict:
    """Возвращает пустой ответ"""
    return {
        "lots": [],
        "count": 0,
        "stats": empty_stats()
    }


def empty_stats() -> Dict:
    """Возвращает пустую статистику"""
    return {
        "price": {},
        "year": {},
        "odometer": {},
        "make": {},
        "model": {},
        "color": {},
        "body_type": {},
        "damage_pr": {},
        "damage_sec": {},
        "status": {},
        "state": {},
        "country": {},
        "risk_index": {}
    }