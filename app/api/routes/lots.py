from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
from uuid import UUID
import json

from app.models.lot import Lot
from app.schemas.lot import LotSchema
from app.enums.auction_type import AuctionType
from app.core.config.redis import get_redis_client

router = APIRouter()

MAX_PAGE_SIZE = 50


def build_cache_key(**kwargs) -> str:
    """
    Формирует уникальный ключ для кэша Redis на основе параметров запроса.

    Args:
        **kwargs: Набор именованных аргументов (фильтры, сортировка и т.д.).

    Returns:
        str: Уникальный строковый ключ вида 'lots:key=value:key2=value2'.
    """
    return "lots:" + ":".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)


@router.get("/", response_model=List[LotSchema])
async def list_lots(
    page: int = Query(1, gt=0, description="Номер страницы (начиная с 1)"),
    limit: int = Query(10, le=MAX_PAGE_SIZE, description="Количество элементов на странице"),
    min_price: Optional[float] = Query(None, description="Минимальная цена лота"),
    max_price: Optional[float] = Query(None, description="Максимальная цена лота"),
    make: Optional[str] = Query(None, description="Марка автомобиля"),
    model: Optional[str] = Query(None, description="Модель автомобиля"),
    year_min: Optional[int] = Query(None, description="Минимальный год выпуска"),
    year_max: Optional[int] = Query(None, description="Максимальный год выпуска"),
    location: Optional[str] = Query(None, description="Местоположение аукциона"),
    damage_type: Optional[str] = Query(None, description="Тип повреждения"),
    status: Optional[str] = Query(None, description="Статус лота (например, 'sold', 'available')"),
    sort: Optional[str] = Query(
        None,
        pattern=r"^(price|end_time|bid_count)_(asc|desc)$",
        description="Поле и направление сортировки: 'price_asc', 'end_time_desc' и т.д."
    ),
    search: Optional[str] = Query(None, description="Полнотекстовый поиск по названию и описанию"),
    redis = Depends(get_redis_client)
):
    """
    Получает список лотов с фильтрацией, пагинацией, сортировкой и кешированием через Redis.

    Args:
        page (int): Номер страницы.
        limit (int): Количество элементов на странице.
        min_price (float, optional): Минимальная цена.
        max_price (float, optional): Максимальная цена.
        make (str, optional): Марка автомобиля.
        model (str, optional): Модель автомобиля.
        year_min (int, optional): Минимальный год выпуска.
        year_max (int, optional): Максимальный год выпуска.
        location (str, optional): Локация аукциона.
        damage_type (str, optional): Тип повреждения.
        status (str, optional): Статус лота.
        sort (str, optional): Ключ сортировки (например, "price_desc").
        search (str, optional): Полнотекстовый поиск.
        redis: Клиент Redis для кеширования.

    Returns:
        List[LotSchema]: Список лотов, удовлетворяющих фильтрам.
    """
    offset = (page - 1) * limit
    cache_key = build_cache_key(
        page=page, limit=limit,
        min_price=min_price, max_price=max_price,
        make=make, model=model,
        year_min=year_min, year_max=year_max,
        location=location, damage_type=damage_type,
        status=status, sort=sort, search=search
    )

    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = Lot.all()

    # Фильтрация по цене
    if min_price is not None:
        query = query.filter(start_price__gte=min_price)
    if max_price is not None:
        query = query.filter(start_price__lte=max_price)

    # Фильтрация по JSON-полям
    if make:
        query = query.filter(auction_data__make=make)
    if model:
        query = query.filter(auction_data__model=model)
    if year_min:
        query = query.filter(auction_data__year__gte=year_min)
    if year_max:
        query = query.filter(auction_data__year__lte=year_max)
    if location:
        query = query.filter(auction_data__location=location)
    if damage_type:
        query = query.filter(auction_data__damage_type=damage_type)
    if status:
        query = query.filter(auction_data__status=status)

    # Сортировка
    if sort:
        field, direction = sort.split("_")
        order_by = {
            "price": "start_price",
            "end_time": "auction_data__end_time",
            "bid_count": "auction_data__bid_count"
        }.get(field)
        if not order_by:
            raise HTTPException(status_code=400, detail="Invalid sort field")
        if direction == "desc":
            order_by = f"-{order_by}"
        query = query.order_by(order_by)

    # Полнотекстовый поиск (PostgreSQL)
    if search:
        query = query.extra(
            where=[
                "to_tsvector('simple', title || ' ' || coalesce(description, '')) @@ plainto_tsquery(%s)"
            ],
            params=[search]
        )

    lots = await query.offset(offset).limit(limit)
    result = [LotSchema.from_orm(l) for l in lots]

    # Кэшируем ответ (TTL — 5 минут)
    await redis.set(cache_key, json.dumps([r.dict() for r in result]), ex=300)
    return result


@router.get("/{lot_id}", response_model=LotSchema)
async def get_lot(lot_id: UUID, redis = Depends(get_redis_client)):
    """
    Получает подробную информацию о конкретном лоте по его UUID.

    Args:
        lot_id (UUID): Уникальный идентификатор лота.
        redis: Клиент Redis для кеширования.

    Returns:
        LotSchema: Объект лота.
    
    Raises:
        HTTPException: Если лот не найден.
    """
    cache_key = f"lot:{lot_id}"
    cached = await redis.get(cache_key)
    if cached:
        return LotSchema.parse_raw(cached)

    lot = await Lot.get_or_none(id=lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    schema = LotSchema.from_orm(lot)
    await redis.set(cache_key, schema.json(), ex=600)  # TTL 10 мин
    return schema


@router.get("/by-auction/{auction_type}", response_model=List[LotSchema])
async def get_lots_by_auction(auction_type: AuctionType, redis = Depends(get_redis_client)):
    """
    Возвращает список лотов, отфильтрованных по типу аукциона (например, COPART, IAAI и т.д.).

    Args:
        auction_type (AuctionType): Тип аукциона (Enum).
        redis: Клиент Redis для кеширования.

    Returns:
        List[LotSchema]: Список лотов указанного типа аукциона.
    """
    cache_key = f"lots:auction_type={auction_type}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    lots = await Lot.filter(auction_type=auction_type)
    result = [LotSchema.from_orm(l) for l in lots]
    await redis.set(cache_key, json.dumps([l.dict() for l in result]), ex=300)
    return result
