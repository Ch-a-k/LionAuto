from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from app.services import get_filtered_lots, add_lot, get_special_filtered_lots, find_lots_by_price_range, count_all_active, count_all_auctions_active
import asyncio
from app.database import init_db, close_db
from loguru import logger
from datetime import datetime
from typing import Union, List, Optional

@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=480,
    time_limit=500
)
def get_refine_task(
    cache = None,
    language: Optional[str] = "en",
    is_historical: Optional[bool] = False,
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

    # Дополнительные фильтры
    state: Optional[List[str]] = None,
    # country: Optional[List[str]] = None,
    is_buynow: Optional[bool] = None,
    min_risk_index: Optional[float] = None,
    max_risk_index: Optional[float] = None,
    auction_date_from: Optional[str] = None,
    auction_date_to: Optional[str] = None,

    # Пагинация и сортировка
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "auction_date",
    sort_order: str = "desc"
):
    """
    Обработчик Celery задачи для фильтрации лотов с поддержкой списков значений.
    """
    logger.debug('try start refine funct')
    async def run():
        await init_db()
        try:
            # Преобразуем даты из строк
            auction_date_from_dt = datetime.fromisoformat(auction_date_from) if auction_date_from else None
            auction_date_to_dt = datetime.fromisoformat(auction_date_to) if auction_date_to else None
            
            result = await get_filtered_lots(
                cache=cache,
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
            return {
                'status': 'completed',
                'result': result,
                'error': None
            }
        except Exception as e:
            logger.error(f"Error in refine task: {str(e)}", exc_info=True)
            if isinstance(e, TypeError) and "unhashable type" in str(e):
                logger.error("Possible dictionary where hashable type expected")
            return {
                'status': 'failed',
                'result': None,
                'error': str(e)
            }
        finally:
            await close_db()

    return asyncio.run(run())


@shared_task(
    autoretry_for=(Exception, MaxRetriesExceededError),
    retry_backoff=True,
    retry_kwargs={'max_retries': 2},
    soft_time_limit=20,
    time_limit=30
)
def add_lot_task(vehicle_data):
    async def run():
        await init_db()  # 🔹 Инициализируем БД

        try:
            lot = await add_lot(vehicle_data)
            return lot
        except MaxRetriesExceededError as e:
            raise e
        except Exception as e:
            raise e
        finally:
            await close_db()  # 🔹 Закрываем соединение

    return asyncio.run(run())

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    time_limit=3600
)
def process_batch_task(self, lots_data):
    """Основная задача для обработки пачки лотов"""
    results = []
    
    async def process():
        await init_db()  # Инициализация подключения
        
        total = len(lots_data)
        
        for i, lot_data in enumerate(lots_data):
            lot_result = None  # сюда положим результат add_lot
            try:
                # Обновляем статус задачи
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'processed': i + 1,
                        'total': total,
                        'current_vin': lot_data.get('vin')
                    }
                )
                
                # Обработка лота
                lot_result = await add_lot(lot_data)

                # add_lot мог вернуть None — считаем это ошибкой
                if not lot_result:
                    raise ValueError("add_lot returned None for VIN "
                                     f"{lot_data.get('vin')}")

                # lot_result — это dict {'id': ..., 'lot_id': ...}
                results.append({
                    'vin': lot_data.get('vin'),
                    'status': 'success',
                    'lot_id': lot_result.get('lot_id'),
                    'id': lot_result.get('id'),
                })
                
            except Exception as e:
                # Логируем с максимально аккуратным доступом к данным
                logger.error(
                    f"Ошибка обработки лота {lot_data.get('vin')}: {e}",
                    exc_info=True,
                )

                lot_id = None
                db_id = None
                if isinstance(lot_result, dict):
                    lot_id = lot_result.get('lot_id')
                    db_id = lot_result.get('id')

                results.append({
                    'vin': lot_data.get('vin'),
                    'status': 'failed',          # ✅ тут точно failed
                    'lot_id': lot_id,
                    'id': db_id,
                    'error': str(e),
                })
        
        return {
            'processed': total,
            'success': sum(1 for r in results if r['status'] == 'success'),
            'failed': sum(1 for r in results if r['status'] == 'failed'),
            'results': results,
        }
    
    # Запускаем асинхронную обработку
    task_result = asyncio.run(process())
    
    # Финализируем статус
    self.update_state(
        state='COMPLETED',
        meta=task_result
    )
    
    return task_result


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=480,
    time_limit=500
)
def get_special_filtered_lots_task(
    is_historical: bool,
    language: str,
    special_filter: list,
    limit: int = 18,
    offset: int = 0
) -> dict:
    """
    Чистая задача для обработки специальных фильтров без кэширования
    """
    try:
        async def run():
            await init_db()
            try:
                # Здесь должна быть основная логика обработки фильтров
                # Например:
                results = await get_special_filtered_lots(
                    is_historical=is_historical,
                    language=language,
                    special_filter=special_filter,
                    limit=limit,
                    offset=offset
                )
                return {
                    'results': results,
                    'count': len(results)
                }
            except Exception as e:
                ...
            finally:
                await close_db()
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"Error in get_special_filtered_lots_task: {str(e)}")
        raise


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=480,
    time_limit=500
)
def get_range_price_lots_task(
    min_price: int,
    max_price: int,
    is_historical: bool,
    language: str,
    limit: int = 18,
    offset: int = 0
) -> dict:
    """
    Чистая задача для обработки специальных фильтров без кэширования
    """
    try:
        async def run():
            await init_db()
            try:
                # Здесь должна быть основная логика обработки фильтров
                # Например:
                results = await find_lots_by_price_range(
                    min_price=min_price,
                    max_price=max_price,
                    is_historical=is_historical,
                    limit=limit,
                    offset=offset,
                    language=language
                )
                return {
                    'results': results,
                    'count': len(results)
                }
            except Exception as e:
                ...
            finally:
                await close_db()
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"Error in get_special_filtered_lots_task: {str(e)}")
        raise


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=480,
    time_limit=500
)
def count_lots_task() -> dict:
    """
    Чистая задача для обработки количества
    """
    try:
        async def run():
            await init_db()
            try:
                # Здесь должна быть основная логика обработки фильтров
                # Например:
                results = await count_all_active()
                return {
                    'results': results,
                }
            except Exception as e:
                ...
            finally:
                await close_db()
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"Error in count_lots_task: {str(e)}")
        raise



@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    soft_time_limit=480,
    time_limit=500
)
def count_auctions_task() -> dict:
    """
    Чистая задача для обработки количества
    """
    try:
        async def run():
            await init_db()
            try:
                # Здесь должна быть основная логика обработки фильтров
                # Например:
                results = await count_all_auctions_active()
                return {
                    'results': results,
                }
            except Exception as e:
                ...
            finally:
                await close_db()
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"Error in count_lots_task: {str(e)}")
        raise