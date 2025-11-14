import httpx
from typing import Union, Dict, Any
from loguru import logger
from app.core.config import settings
from app.schemas import VehicleModel, VehicleModelOther
from app.services import delete_lot
from app.database import init_db, close_db
import asyncio

headers = {
    "api-key": settings.api_apicar_key,
}

async def fetch_lots() -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Получает данные по лотам.

    Args:
        page (int): Номер страницы.
        size (int): Количество лотов на странице.

    Returns:
        Union[Dict[str, Any], Dict[str, str]]: JSON-ответ API или сообщение об ошибке.
    """
    url = f"https://api.apicar.store/api/cars/deleted"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching: {str(e)}")
            return {"error": str(e)}
        
async def process_lot(lot_id: int) -> bool:
    """Обрабатывает и сохраняет один лот."""
    try:
        if not lot_id:
            logger.error("Received None lot data")
            return False
        await delete_lot(lot_id=lot_id)
       
        return True
    except Exception as e:
        logger.error(f"Error processing lot {lot_id}: {str(e)}")
        return False
    

async def main():
    await init_db()
    
    # Получаем общее количество страниц
    result = await fetch_lots()
    success_count = 0
    
    for lot in result['data']:
        if await process_lot(lot['lot_id']):
            success_count += 1
   
    await close_db()

if __name__ == "__main__":
    asyncio.run(main())