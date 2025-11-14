import httpx
from typing import Union, Dict, Any
from loguru import logger
from app.core.config import settings
from app.schemas import VehicleModel, VehicleModelOther
from app.services import update_lot
from app.database import init_db, close_db
import asyncio

headers = {
    "api-key": settings.api_apicar_key,
}

async def fetch_lots(page: int, size: int) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Получает данные по лотам.

    Args:
        page (int): Номер страницы.
        size (int): Количество лотов на странице.

    Returns:
        Union[Dict[str, Any], Dict[str, str]]: JSON-ответ API или сообщение об ошибке.
    """
    url = f"https://api.apicar.store/api/cars/db/update?page={page}&size={size}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching page {page}: {str(e)}")
            return {"error": str(e)}
        
async def process_lot(lot: Dict[str, Any]) -> bool:
    """Обрабатывает и сохраняет один лот."""
    try:
        if not lot:
            logger.error("Received None lot data")
            return False
        if len(lot.get("vin")) == 17:
            model_validate = VehicleModel
        else:
            model_validate = VehicleModelOther
        
        new_lot = model_validate(
            lot_id=lot.get("lot_id"),
            base_site=lot.get("base_site"),
            odometer=lot.get("odometer", 0),
            price=lot.get("price", 0),
            reserve_price=lot.get("reserve_price", 0),
            bid=lot.get("current_bit", 0),
            auction_date=lot.get("auction_date", None),
            cost_repair=lot.get("cost_repair", 0),
            year=lot.get("year"),
            cylinders=lot.get("cylinders"),
            state=lot.get("state"),
            vehicle_type=lot.get("vehicle_type"),       
            make=lot.get("make"),
            model=lot.get("model"),
            damage_pr=lot.get("damage_pr"),
            damage_sec=lot.get("damage_sec"),
            keys=lot.get("keys"),
            odobrand=lot.get("odobrand"),
            fuel=lot.get("fuel"),
            drive=lot.get("drive"),
            transmission=lot.get("transmission"),
            color=lot.get("color"),
            status=lot.get("status"),
            auction_status="Not Sold",
            body_type=lot.get("body_type"),
            series=lot.get("series"),
            title=lot.get("title"),
            vin=lot.get("vin"),
            engine=lot.get("engine"),
            engine_size=lot.get("engine_size"),
            location=lot.get("location"),
            location_old=lot.get("location_old"),
            country=lot.get("country"),
            document=lot.get("document"),
            document_old=lot.get("document_old"),
            seller=lot.get("seller"),
            image_thubnail=lot.get("link_img_small")[0] if lot.get("link_img_small") else None,
            is_buynow=lot.get("is_buynow", False),
            link_img_hd=lot.get("link_img_hd", []),
            link_img_small=lot.get("link_img_small", []),
            link=lot.get("link"),
            seller_type=lot.get("seller_type"),
            risk_index=lot.get("risk_index"),
            is_historical=lot.get("is_historical", False)
        )
        
        lot_dict = new_lot.model_dump()
        await update_lot(vehicle_data=lot_dict)
       
        return True
    except Exception as e:
        logger.error(f"Error processing lot {lot.get('lot_id')}: {str(e)}")
        return False
    

async def main():
    await init_db()
    batch_size = 100  # Фиксированный размер пачки
    
    # Получаем общее количество страниц
    first_check = await fetch_lots(1, batch_size)
    max_pages = first_check['pages']
    
    try:
        current_page = 1
        while current_page <= max_pages:
            # Определяем страницы для текущего пакета (макс. 3)
            pages_to_fetch = [
                page for page in range(current_page, current_page + 3) 
                if page <= max_pages
            ]
            
            if not pages_to_fetch:
                break
            
            # Запускаем параллельные запросы
            tasks = [
                fetch_lots(page, batch_size)
                for page in pages_to_fetch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обрабатываем результаты
            for page, result in zip(pages_to_fetch, results):
                if isinstance(result, Exception):
                    logger.error(f"Error on page {page}: {result}")
                    continue
                
                if "error" in result:
                    logger.error(f"API error on page {page}: {result['error']}")
                    continue
                
                if not result.get("data"):
                    logger.info(f"No data on page {page}")
                    continue
                
                # Обработка лотов
                success_count = 0
                for lot in result['data']:
                    if await process_lot(lot):
                        success_count += 1
                
                logger.info(f"Page {page} done. Success: {success_count}/{len(result['data'])}")
            
            # Переходим к следующей тройке страниц
            current_page += 3
            
            # Ждем 1 секунду перед следующим пакетом (если еще есть страницы)
            if current_page <= max_pages:
                await asyncio.sleep(1)
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await close_db()
        logger.info("Database connection closed")

if __name__ == "__main__":
    asyncio.run(main())