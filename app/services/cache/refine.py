import asyncio
import json
from aiocache import caches
from app.core.config import settings
from app.tasks import get_refine_task, get_special_filtered_lots_task, get_range_price_lots_task, count_lots_task, count_auctions_task
from loguru import logger
from celery.result import AsyncResult
from typing import Optional, Dict, Any
from datetime import datetime

# Initialize cache
cache = caches.get("default")

# Limit concurrent tasks
semaphore = asyncio.BoundedSemaphore(8)

# Filter configurations
SPECIAL_FILTERS = [
    "buy_now", "keys", "minimum_odometer", "maximum_odometer",
    "document_clean", "auction_date_today", "auction_date_tomorrow",
    "auction_next_week", "run-and-drive"
]

RANGE_PRICE = [
    [1, 7000],
    [7000, 10000],
    [10000, 15000],
    [15000, 20000],
    [20000, 30000],
    [30000, 500000]
]

SORT_BY = [
    "auction_date", "price", "year", "odometer", "created_at", "bid", "current_bid", "reserve_price"
]

def safe_serialize(data: Any) -> str:
    """Safely serialize data for caching with comprehensive type handling"""
    if data is None:
        return json.dumps({})
    if isinstance(data, (str, int, float, bool)):
        return json.dumps(data)
    if isinstance(data, (dict, list)):
        try:
            return json.dumps(data)
        except TypeError:
            try:
                return json.dumps(data, default=lambda x: str(x) if not isinstance(x, (type(None), str, int, float, bool)) else x)
            except Exception as e:
                logger.warning(f"Serialization fallback failed: {e}")
                return json.dumps({})
    try:
        return json.dumps(data, default=str)
    except Exception as e:
        logger.warning(f"Serialization error: {e}")
        return json.dumps({})

async def refresh_single_cache(
        i: int, 
        lang: str, 
        history: bool, 
        site: Optional[str] = None,
        sort_by: Optional[str] = "auction_date",
        format_sort: Optional[str] = "desc"
        ) -> None:
    async with semaphore:
        try:
            task_kwargs: Dict[str, Any] = {
                "is_historical": history,
                "language": lang,
                "vehicle_type_slug": ["automobile"],
                "limit": 18,
                "offset": i,
                "sort_by": sort_by,
                "sort_order": format_sort,
            }
            if site:
                task_kwargs["base_site"] = site

            task = get_refine_task.apply_async(kwargs=task_kwargs)
            
            for _ in range(30):  # max_retries
                task_result = AsyncResult(task.id)
                if task_result.ready():
                    if task_result.successful():
                        result = task_result.result
                        if not isinstance(result, dict):
                            logger.warning(f"Unexpected result type: {type(result)}")
                            result = {}
                        
                        cache_data = result.get('result', {})
                        key = f"{site or ''}{settings.CACHE_KEY}{i}{lang}{'history' if history else 'active'}{sort_by}{format_sort}"
                        await cache.set(key, safe_serialize(cache_data), ttl=settings.CACHE_TTL + 180)
                        return
                    else:
                        logger.error(f"Task failed: {task_result.result}")
                        return
                await asyncio.sleep(1)  # retry_delay
            
            logger.error(f"Task timeout for [{i}][{lang}][{history}]")
                
        except Exception as e:
            logger.error(f"Cache refresh error [{i}][{lang}][{history}]: {e}")

async def refresh_special_filters_cache(i: int, lang: str, history: bool, filter_name: str) -> None:
    async with semaphore:
        try:
            task = get_special_filtered_lots_task.apply_async(kwargs={
                "is_historical": history,
                "language": lang,
                "special_filter": [filter_name],
                "limit": 18,
                "offset": i
            })
            
            for _ in range(30):
                task_result = AsyncResult(task.id)
                if task_result.ready():
                    if task_result.successful():
                        result = task_result.result
                        key = f"{settings.CACHE_KEY}_{filter_name}_{i}_{lang}_{'nonactive' if history else 'active'}"
                        await cache.set(key, safe_serialize(result), ttl=settings.CACHE_TTL + 180)
                        return
                    else:
                        logger.error(f"Filter task failed {filter_name}: {task_result.result}")
                        return
                await asyncio.sleep(1)
            
            logger.error(f"Filter task timeout [{i}][{lang}][{filter_name}]")
                
        except Exception as e:
            logger.error(f"Filter cache error {filter_name}: {e}")

async def refresh_price_range_cache(min_price: int, max_price: int, i: int, lang: str, history: bool) -> None:
    async with semaphore:
        try:
            task = get_range_price_lots_task.apply_async(kwargs={
                "is_historical": history,
                "language": lang,
                "min_price": min_price,
                "max_price": max_price,
                "limit": 18,
                "offset": i
            })
            
            for _ in range(30):
                task_result = AsyncResult(task.id)
                if task_result.ready():
                    if task_result.successful():
                        key = f"{settings.CACHE_KEY}_min_price{min_price}max_price{max_price}{i}"
                        await cache.set(key, safe_serialize(task_result.result), ttl=settings.CACHE_TTL + 180)
                        return
                    else:
                        logger.error(f"Price task failed {min_price}-{max_price}: {task_result.result}")
                        return
                await asyncio.sleep(1)
            
            logger.error(f"Price task timeout [{i}][{min_price}-{max_price}]")
                
        except Exception as e:
            logger.error(f"Price cache error {min_price}-{max_price}: {e}")

async def refresh_active_count_cache() -> None:
    async with semaphore:
        task_key = "all_active_count_task"
        try:
            if await cache.get(task_key):
                logger.debug("Count refresh already in progress")
                return
            
            await cache.set(task_key, "1", ttl=300)
            task = count_lots_task.apply_async()

            for _ in range(30):
                task_result = AsyncResult(task.id)
                if task_result.ready():
                    if task_result.successful():
                        await cache.set("all_active_count", safe_serialize(task_result.result), ttl=300)
                        logger.info("Active count updated")
                        break
                    else:
                        logger.error(f"Count task failed: {task_result.result}")
                        break
                await asyncio.sleep(1)
            else:
                logger.error("Count task timeout")
            
        except Exception as e:
            logger.error(f"Count cache error: {e}")
        finally:
            await cache.delete(task_key)

async def refresh_auction_active_count_cache() -> None:
    async with semaphore:
        task_key = "all_auction_active_count_task"
        try:
            if await cache.get(task_key):
                logger.debug("Count refresh already in progress")
                return
            
            await cache.set(task_key, "1", ttl=300)
            task = count_auctions_task.apply_async()

            for _ in range(30):
                task_result = AsyncResult(task.id)
                if task_result.ready():
                    if task_result.successful():
                        await cache.set("all_auction_active_count", safe_serialize(task_result.result), ttl=300)
                        logger.info("Active count updated")
                        break
                    else:
                        logger.error(f"Count task failed: {task_result.result}")
                        break
                await asyncio.sleep(1)
            else:
                logger.error("Count task timeout")
            
        except Exception as e:
            logger.error(f"Count cache error: {e}")
        finally:
            await cache.delete(task_key)

async def schedule_count_refresh() -> None:
    """Regular count refresh every 5 minutes"""
    while True:
        try:
            await refresh_active_count_cache()
            await refresh_auction_active_count_cache()
        except Exception as e:
            logger.error(f"Count scheduler error: {e}")
        await asyncio.sleep(300)

async def execute_tasks_in_batches(tasks: list, batch_size: int = 20) -> None:
    """Execute tasks in controlled batches"""
    for i in range(0, len(tasks), batch_size):
        try:
            await asyncio.gather(*tasks[i:i + batch_size])
            await asyncio.sleep(0.5)  # Brief pause between batches
        except Exception as e:
            logger.error(f"Task batch error: {e}")

async def refresh_lot_cache() -> None:
    """Main cache refresh loop"""
    while True:
        try:
            start_time = datetime.now()
            tasks = []
            
            # Generate all task combinations
            for i in range(7):
                for lang in ['ru', 'en', 'md', 'ua', 'kz', 'pl']:
                    for history in [False, True]:
                        # Standard queries
                        for site in ['iaai', 'copart', '']:
                            for sort in SORT_BY:
                                for order in ['asc', 'desc']:
                                    tasks.append(refresh_single_cache(
                                        i, lang, history, site, sort, order
                                    ))
                        
                        # Special filters
                        for filter_name in SPECIAL_FILTERS:
                            tasks.append(refresh_special_filters_cache(
                                i, lang, history, filter_name
                            ))
                        
                        # Price ranges
                        for min_p, max_p in RANGE_PRICE:
                            tasks.append(refresh_price_range_cache(
                                min_p, max_p, i, lang, history
                            ))
            
            # Execute in managed batches
            await execute_tasks_in_batches(tasks)
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Cache refresh cycle completed in {duration:.2f} seconds")
            
            # Calculate sleep time based on remaining TTL
            sleep_time = max(10, settings.CACHE_TTL - duration - 10)
            await asyncio.sleep(sleep_time)
            
        except Exception as e:
            logger.error(f"Cache refresh error: {e}")
            await asyncio.sleep(60)

async def init_main_cache() -> None:
    """Initialize all cache refresh processes"""
    try:
        await asyncio.gather(
            schedule_count_refresh(),
            refresh_lot_cache()
        )
    except Exception as e:
        logger.error(f"Fatal cache initialization error: {e}")
        raise