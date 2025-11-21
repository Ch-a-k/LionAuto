from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Form, Depends, Request
from math import ceil
from app.models import Lot, HistoricalLot, Translation, LanguageEnum, Status, VehicleType, Make, Color, LotWithoutAuctionDate
from app.schemas import TransLiteral, TranslationUpdateRequest
from app.services import serialize_lot, get_count_lot
from loguru import logger
from pydantic import BaseModel
from typing import List, Optional, Dict, Union
from datetime import datetime, timedelta
from tortoise.functions import Count
from tortoise.exceptions import DoesNotExist
from tortoise import Tortoise
from uuid import uuid4
from pathlib import Path
import aiofiles
from app.core.config import settings
from app.services.store.s3contabo import s3_service
import boto3
import io

router = APIRouter()

@router.get("/get_catalog")
async def get_lots_catalog(
    page: int = Query(1, ge=1, description="Номер страницы, начиная с 1"),
    per_page: int = Query(20, ge=1, le=100, description="Количество элементов на странице (1-100)"),
    is_historical: bool = Query(False),
    language: TransLiteral | None = Query(None),
):
    """
    Получение каталога лотов с пагинацией.

    Работает:
    - для актуальных лотов: по ВСЕМ шарам Lot1..Lot7 через Lot.count_across_shards / Lot.query_across_shards_with_limit_offset
    - для исторических: по таблице HistoricalLot через historical_count / historical_query_with_limit_offset
    """
    try:
        # ---------- 1. Считаем общее количество ----------
        if is_historical:
            # Исторические – отдельная таблица без шардов
            total = await HistoricalLot.historical_count()
        else:
            # Актуальные – по всем шард-таблицам Lot1..Lot7
            total = await Lot.count_across_shards()

        # Общее количество страниц
        total_pages = ceil(total / per_page) if total > 0 else 0

        # Если вообще нет данных
        if total == 0:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0,
            }

        # Проверяем, что запрашиваемая страница существует
        if page > total_pages:
            raise HTTPException(status_code=404, detail="Страница не найдена")

        # ---------- 2. Offset/limit ----------
        offset = (page - 1) * per_page

        if is_historical:
            # Исторические – собственные хелперы
            lots = await HistoricalLot.historical_query_with_limit_offset(
                limit=per_page,
                offset=offset,
            )
        else:
            # Актуальные – шардированные Lot1..Lot7
            lots = await Lot.query_across_shards_with_limit_offset(
                limit=per_page,
                offset=offset,
            )

        # ---------- 3. Сериализация + переводы ----------
        # serialize_lot сам уже должен уметь переводить справочники по language
        formatted_lots = [await serialize_lot(language, lot) for lot in lots]

        return {
            "items": formatted_lots,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    

@router.get("/translations")
async def get_all_translations():
    """
    Получает все переводы и группирует их по field_name.
    
    Возвращает:
        dict: Переводы, сгруппированные по полю field_name, с переводами для каждого original_value.
    """
    try:
        # Получаем все переводы из базы данных
        translations = await Translation.all()

        # Структура данных для ответа
        grouped_translations = {}

        # Обрабатываем переводы и группируем их по field_name
        for translation in translations:
            # Если field_name еще не существует в группе, создаем новый список
            if translation.field_name not in grouped_translations:
                grouped_translations[translation.field_name] = {}

            # Если original_value еще не существует, создаем новый список
            if translation.original_value not in grouped_translations[translation.field_name]:
                grouped_translations[translation.field_name][translation.original_value] = []

            # Добавляем перевод для конкретного original_value
            grouped_translations[translation.field_name][translation.original_value].append({
                "language": translation.language,
                "translated_value": translation.translated_value
            })

        return grouped_translations

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching translations: {str(e)}")


@router.put("/translations")
async def update_translation(request: TranslationUpdateRequest):
    """
    Обновляет переводы для конкретного поля и оригинального значения.
    
    Аргументы:
        request (TranslationUpdateRequest): Запрос с переводами.
    
    Возвращает:
        dict: Обновленные переводы.
    """
    try:
        # Проверка всех языков
        for lang, translation in request.translations.items():
            if not LanguageEnum.is_valid(lang):
                raise HTTPException(status_code=400, detail=f"Invalid language code: {lang}")
        
        # Получаем все переводы для данного field_name и original_value
        existing_translations = await Translation.filter(
            field_name=request.field_name, original_value=request.original_value
        )

        # Если переводы не найдены, возвращаем ошибку
        if not existing_translations:
            raise HTTPException(status_code=404, detail="Translation not found")

        # Обновляем переводы для каждого языка
        for translation in existing_translations:
            if translation.language.value in request.translations:
                translation.translated_value = request.translations[translation.language.value]
                await translation.save()

        # Возвращаем обновленные переводы
        updated_translations = await Translation.filter(
            field_name=request.field_name, original_value=request.original_value
        )
        grouped_translations = {
            translation.language.value: translation.translated_value
            for translation in updated_translations
        }

        return {
            "field_name": request.field_name,
            "original_value": request.original_value,
            "translations": grouped_translations
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/count/lots")
async def count_lots():
    return await get_count_lot(lot=True)

@router.get("/count/lots_without_date")
async def count_lota_without_date():
    return await get_count_lot()

@router.get("/count/lots_historical")
async def counts_historical_lots():
    return await get_count_lot(historical=True)


class VehicleTypeStats(BaseModel):
    type: str
    count: int

@router.get("/stats/vehicle_types", response_model=List[VehicleTypeStats])
async def get_vehicle_types_stats():
    """
    Возвращает статистику по типам транспортных средств.
    """
    stats = {}
    
    # 1. Запрос для Lot
    lot_counts = await Lot.annotate(
        count=Count('id')
    ).group_by('vehicle_type__name').values(
        'vehicle_type__name', 
        'count'
    )
    
    for item in lot_counts:
        if item['vehicle_type__name']:
            stats[item['vehicle_type__name']] = stats.get(item['vehicle_type__name'], 0) + item['count']
    
    # 2. Запрос для HistoricalLot
    historical_counts = await HistoricalLot.annotate(
        count=Count('id')
    ).group_by('vehicle_type__name').values(
        'vehicle_type__name', 
        'count'
    )
    
    for item in historical_counts:
        if item['vehicle_type__name']:
            stats[item['vehicle_type__name']] = stats.get(item['vehicle_type__name'], 0) + item['count']
    
    # 3. Запрос для LotWithoutAuctionDate
    without_date_counts = await LotWithoutAuctionDate.annotate(
        count=Count('id')
    ).group_by('vehicle_type__name').values(
        'vehicle_type__name', 
        'count'
    )
    
    for item in without_date_counts:
        if item['vehicle_type__name']:
            stats[item['vehicle_type__name']] = stats.get(item['vehicle_type__name'], 0) + item['count']
    
    # Форматируем результат
    result = [
        VehicleTypeStats(type=k, count=v)
        for k, v in stats.items()
    ]
    
    # Сортируем по убыванию количества
    result.sort(key=lambda x: x.count, reverse=True)
    
    return result


@router.get("/stats/vehicle_types/optimized", response_model=List[Dict[str, int]])
async def get_vehicle_types_stats_optimized():
    """
    Оптимизированная версия с использованием UNION для всех таблиц
    """
    query = """
    SELECT vt.name as vehicle_type, COUNT(*) as count FROM (
        SELECT vehicle_type_id FROM lot
        UNION ALL
        SELECT vehicle_type_id FROM historical_lot
        UNION ALL
        SELECT vehicle_type_id FROM lot_without_auction_date
    ) as all_lots
    JOIN vehicle_type vt ON vt.id = all_lots.vehicle_type_id
    GROUP BY vt.name
    ORDER BY count DESC
    """
    
    stats = await Lot.raw(query)
    return [{"type": item["vehicle_type"], "count": item["count"]} for item in stats]


class AuctionStats(BaseModel):
    name: str
    count: int

@router.get("/stats/auctions", response_model=List[AuctionStats])
async def get_auctions_stats():
    """
    Возвращает статистику по аукционам (base_site) из всех таблиц лотов.
    Включает данные из:
    - Lot (активные лоты)
    - HistoricalLot (исторические лоты)
    - LotWithoutDate (лоты без даты аукциона)
    """
    stats = {}
    
    # 1. Получаем данные из таблицы Lot
    lot_counts = await Lot.annotate(
        count=Count('id')
    ).group_by('base_site__name').values(
        'base_site__name', 
        'count'
    )
    
    for item in lot_counts:
        if item['base_site__name']:
            stats[item['base_site__name']] = stats.get(item['base_site__name'], 0) + item['count']
    
    # 2. Получаем данные из таблицы HistoricalLot
    historical_counts = await HistoricalLot.annotate(
        count=Count('id')
    ).group_by('base_site__name').values(
        'base_site__name', 
        'count'
    )
    
    for item in historical_counts:
        if item['base_site__name']:
            stats[item['base_site__name']] = stats.get(item['base_site__name'], 0) + item['count']
    
    # 3. Получаем данные из таблицы LotWithoutAuctionDate
    without_date_counts = await LotWithoutAuctionDate.annotate(
        count=Count('id')
    ).group_by('base_site__name').values(
        'base_site__name', 
        'count'
    )
    
    for item in without_date_counts:
        if item['base_site__name']:
            stats[item['base_site__name']] = stats.get(item['base_site__name'], 0) + item['count']
    
    # Форматируем результат
    result = [
        AuctionStats(name=k, count=v)
        for k, v in stats.items()
    ]
    
    # Сортируем по убыванию количества
    result.sort(key=lambda x: x.count, reverse=True)
    
    return result


@router.get("/stats/auctions/optimized", response_model=List[AuctionStats])
async def get_auctions_stats_optimized():
    """
    Оптимизированная версия с использованием UNION для всех таблиц
    """
    query = """
    SELECT bs.name as auction_name, COUNT(*) as count 
    FROM (
        SELECT base_site_id FROM lot WHERE base_site_id IS NOT NULL
        UNION ALL
        SELECT base_site_id FROM historical_lot WHERE base_site_id IS NOT NULL
        UNION ALL
        SELECT base_site_id FROM lot_without_auction_date WHERE base_site_id IS NOT NULL
    ) as all_lots
    JOIN base_site bs ON bs.id = all_lots.base_site_id
    GROUP BY bs.name
    ORDER BY count DESC
    """
    
    stats = await Lot.raw(query)
    return [AuctionStats(name=item["auction_name"], count=item["count"]) for item in stats]


@router.get("/stats/monthly_trends", response_model=List[Dict[str, Union[str, int]]])
async def get_monthly_trends(
    months: Optional[int] = Query(default=6, gt=0, le=36)
):
    """
    Возвращает месячные тренды количества лотов за указанный период.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30*months)
    
    # Проверяем наличие данных
    check_query = """
    SELECT 
        MIN(auction_date) as min_date,
        MAX(auction_date) as max_date,
        COUNT(*) as total_count
    FROM lot
    """
    conn = Tortoise.get_connection("default")
    stats = await conn.execute_query_dict(check_query)

    # Основной запрос (оптимизированный под ваши данные)
    query = """
    WITH months AS (
        SELECT to_char(date_trunc('month', month::date), 'YYYY-MM') as month
        FROM generate_series(
            date_trunc('month', $1::timestamp),
            date_trunc('month', $2::timestamp),
            interval '1 month'
        ) as month
    ),
    all_lots AS (
        SELECT auction_date FROM lot
        UNION ALL
        SELECT auction_date FROM historical_lot
        UNION ALL
        SELECT auction_date FROM lot_without_auction_date
    ),
    grouped_lots AS (
        SELECT to_char(date_trunc('month', auction_date), 'YYYY-MM') as month
        FROM all_lots
        WHERE auction_date IS NOT NULL
    )
    SELECT 
        m.month,
        COUNT(gl.month) as count
    FROM months m
    LEFT JOIN grouped_lots gl ON gl.month = m.month
    GROUP BY m.month
    ORDER BY m.month
    """
    
    results = await conn.execute_query_dict(query, [start_date, end_date])
    
    return results



@router.get("/stats/monthly_trends_test")
async def test_query():
    """Тестовый запрос для проверки работы с базой"""
    conn = Tortoise.get_connection("default")
    # Простейший запрос для проверки
    result = await conn.execute_query_dict("SELECT to_char(auction_date, 'YYYY-MM') as month FROM lot LIMIT 10")
    return {"data": result}


class StatusOut(BaseModel):
    id: int
    slug: Optional[str] = None
    name: Optional[str] = None
    hex: Optional[str] = None
    letter: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True

class VehicleTypeOut(BaseModel):
    id: Optional[int] = None
    slug: Optional[str] = None
    name: Optional[str] = None
    icon_path: Optional[str] = None
    icon_disable: Optional[str] = None
    icon_active: Optional[str] = None

    class Config:
        from_attributes = True

class MakeOut(BaseModel):
    id: int
    slug: Optional[str] = None
    name: Optional[str] = None
    vehicle_type_id: int
    popular_counter: int
    icon_path: Optional[str] = None

    class Config:
        from_attributes = True

class ColorOut(BaseModel):
    id: int
    slug: Optional[str] = None
    name: Optional[str] = None
    hex: Optional[str] = None

    class Config:
        from_attributes = True

# Модели для создания/обновления
class StatusCreateUpdate(BaseModel):
    slug: Optional[str] = None
    name: Optional[str] = None
    hex: Optional[str] = None
    letter: Optional[str] = None
    description: Optional[str] = None

class VehicleTypeCreateUpdate(BaseModel):
    slug: Optional[str] = None
    name: Optional[str] = None
    icon_path: Optional[str] = None
    icon_active: Optional[str] = None
    icon_disable: Optional[str] = None

class MakeCreateUpdate(BaseModel):
    slug: Optional[str] = None
    name: Optional[str] = None
    vehicle_type_id: int
    popular_counter: int = 0
    icon_path: Optional[str] = None

class ColorCreateUpdate(BaseModel):
    slug: Optional[str] = None
    name: Optional[str] = None
    hex: Optional[str] = None

# Эндпоинты для статусов
@router.get("/reference/status", response_model=List[StatusOut])
async def get_reference_status(lot_type: str = None):
    query = Status.all()
    if lot_type:
        # Пример фильтрации для TortoiseORM
        pass
    statuses = await query
    return [StatusOut.from_orm(status) for status in statuses]

@router.post("/reference/status", response_model=StatusOut)
async def create_status(status_data: StatusCreateUpdate):
    status_obj = await Status.create(**status_data.dict())
    return StatusOut.from_orm(status_obj)

@router.put("/reference/status/{status_id}", response_model=StatusOut)
async def update_status(status_id: int, status_data: StatusCreateUpdate):
    try:
        status_obj = await Status.get(id=status_id)
        await status_obj.update_from_dict(status_data.dict()).save()
        return StatusOut.from_orm(status_obj)
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Status not found")

@router.delete("/reference/status/{status_id}")
async def delete_status(status_id: int):
    deleted_count = await Status.filter(id=status_id).delete()
    if not deleted_count:
        raise HTTPException(status_code=404, detail="Status not found")
    return {"message": "Status deleted successfully"}

# Эндпоинты для типов транспорта
@router.get("/reference/vehicle_type", response_model=List[VehicleTypeOut])
async def get_reference_vehicle_type(lot_type: Optional[str] = None):
    query = VehicleType.all()
    if lot_type:
        pass  # Фильтрация если нужно
    vehicle_types = await query
    return [VehicleTypeOut.from_orm(vt) for vt in vehicle_types]

import traceback

@router.get("/admin/healthcheck/s3")
async def healthcheck_s3():
    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
            config=boto3.session.Config(signature_version='s3v4')
        )
        s3.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        response = s3.list_buckets()
        return {"status": "ok", "buckets": [b['Name'] for b in response['Buckets']]}
    except Exception as e:
        traceback_str = traceback.format_exc()
        return {"status": "error", "detail": str(e), "trace": traceback_str}

async def upload_to_s3(file: UploadFile) -> str:
    try:
        ext = file.filename.split('.')[-1]
        key = f"vehicle_type_icons/{uuid4()}.{ext}"

        await file.seek(0)
        file_content = await file.read()
        if not file_content:
            raise ValueError("Uploaded file is empty")

        file_stream = io.BytesIO(file_content)

        s3_service.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=file_stream,
            ACL='public-read',
            ContentType=file.content_type,
        )

        return f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_NAME}/{key}"
    except Exception as e:
        logger.error(f"❌ S3 upload failed: {str(e)} | File: {file.filename}")
        raise RuntimeError(f"Upload failed: {str(e)}")

@router.post("/reference/vehicle_type", response_model=VehicleTypeOut)
async def create_vehicle_type_with_icons(
    name: str = Form(...),
    slug: str = Form(...),
    icon_file: Optional[UploadFile] = File(None),
    icon_active: Optional[UploadFile] = File(None),
    icon_disable: Optional[UploadFile] = File(None),
):

    # Загружаем каждый файл (если есть)
    icon_path_url = await upload_to_s3(icon_file) if icon_file else None
    icon_active_url = await upload_to_s3(icon_active) if icon_active else None
    icon_disable_url = await upload_to_s3(icon_disable) if icon_disable else None

    # Сохраняем в БД
    vehicle_type_obj = await VehicleType.create(
        name=name,
        slug=slug,
        icon_path=icon_path_url,
        icon_active=icon_active_url,
        icon_disable=icon_disable_url,
    )

    return VehicleTypeOut.from_orm(vehicle_type_obj)


UPLOAD_DIR = Path("app/static/vehicle_icons")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://0.0.0.0:8000"  # желательно вынести в настройки

class VehicleTypeCreateUpdateBytes:
    def __init__(
        self,
        slug: str = Form(None),
        name: str = Form(None),
        icon_path: UploadFile = File(None),
        icon_active: UploadFile = File(None),
        icon_disable: UploadFile = File(None),
    ):
        self.slug = slug
        self.name = name
        self.icon_path = icon_path
        self.icon_active = icon_active
        self.icon_disable = icon_disable

async def save_icon(upload_file: UploadFile, subfolder: str) -> str:
    filename = f"{uuid4().hex}_{upload_file.filename}"
    dest_dir = UPLOAD_DIR / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = dest_dir / filename

    try:
        async with aiofiles.open(file_path, "wb") as f:
            content = await upload_file.read()
            await f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")

    return f"https://api.factum-auto.com/static/vehicle_icons/{subfolder}/{filename}"


@router.put("/reference/vehicle_type/{vehicle_type_id}", response_model=VehicleTypeOut)
async def update_vehicle_type(
    vehicle_type_id: int,
    request: Request,
    vehicle_data: VehicleTypeCreateUpdateBytes = Depends()
):
    try:
        vehicle = await VehicleType.get(id=vehicle_type_id)
        data = {}

        if vehicle_data.slug:
            data["slug"] = vehicle_data.slug
        if vehicle_data.name:
            data["name"] = vehicle_data.name
        if vehicle_data.icon_path:
            data["icon_path"] = await save_icon(vehicle_data.icon_path, "icon_path")
        if vehicle_data.icon_active:
            data["icon_active"] = await save_icon(vehicle_data.icon_active, "icon_active")
        if vehicle_data.icon_disable:
            data["icon_disable"] = await save_icon(vehicle_data.icon_disable, "icon_disable")

        await vehicle.update_from_dict(data).save()
        return VehicleTypeOut.from_orm(vehicle)

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Vehicle type not found")

@router.delete("/reference/vehicle_type/{vehicle_type_id}")
async def delete_vehicle_type(vehicle_type_id: int):
    deleted_count = await VehicleType.filter(id=vehicle_type_id).delete()
    if not deleted_count:
        raise HTTPException(status_code=404, detail="Vehicle type not found")
    return {"message": "Vehicle type deleted successfully"}

# Эндпоинты для марок
@router.get("/reference/make", response_model=List[MakeOut])
async def get_reference_make(
    vehicle_type_id: Optional[int] = None,
    lot_type: Optional[str] = None
):
    query = Make.all()
    if vehicle_type_id:
        query = query.filter(vehicle_type_id=vehicle_type_id)
    if lot_type:
        pass  # Фильтрация если нужно
    makes = await query
    return [MakeOut.from_orm(make) for make in makes]

@router.post("/reference/make", response_model=MakeOut)
async def create_make(make_data: MakeCreateUpdate):
    # Проверяем существование типа транспорта
    if not await VehicleType.filter(id=make_data.vehicle_type_id).exists():
        raise HTTPException(status_code=400, detail="Vehicle type not found")
    
    make_obj = await Make.create(**make_data.dict())
    return MakeOut.from_orm(make_obj)

@router.put("/reference/make/{make_id}", response_model=MakeOut)
async def update_make(make_id: int, make_data: MakeCreateUpdate):
    try:
        # Проверяем существование типа транспорта
        if not await VehicleType.filter(id=make_data.vehicle_type_id).exists():
            raise HTTPException(status_code=400, detail="Vehicle type not found")
            
        make_obj = await Make.get(id=make_id)
        await make_obj.update_from_dict(make_data.dict()).save()
        return MakeOut.from_orm(make_obj)
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Make not found")

@router.delete("/reference/make/{make_id}")
async def delete_make(make_id: int):
    deleted_count = await Make.filter(id=make_id).delete()
    if not deleted_count:
        raise HTTPException(status_code=404, detail="Make not found")
    return {"message": "Make deleted successfully"}

# Эндпоинты для цветов
@router.get("/reference/color", response_model=List[ColorOut])
async def get_reference_color(lot_type: Optional[str] = None):
    query = Color.all()
    if lot_type:
        pass  # Фильтрация если нужно
    
    colors = await query
    # Гарантируем, что hex будет строкой (даже если в базе NULL)
    return [ColorOut(
        id=color.id,
        slug=color.slug,
        name=color.name,
        hex=color.hex or '#000000'  # Заменяем NULL на дефолтное значение
    ) for color in colors]

@router.post("/reference/color", response_model=ColorOut)
async def create_color(color_data: ColorCreateUpdate):
    color_obj = await Color.create(**color_data.dict())
    return ColorOut.from_orm(color_obj)

@router.put("/reference/color/{color_id}", response_model=ColorOut)
async def update_color(color_id: int, color_data: ColorCreateUpdate):
    try:
        color_obj = await Color.get(id=color_id)
        await color_obj.update_from_dict(color_data.dict()).save()
        return ColorOut.from_orm(color_obj)
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Color not found")

@router.delete("/reference/color/{color_id}")
async def delete_color(color_id: int):
    deleted_count = await Color.filter(id=color_id).delete()
    if not deleted_count:
        raise HTTPException(status_code=404, detail="Color not found")
    return {"message": "Color deleted successfully"}