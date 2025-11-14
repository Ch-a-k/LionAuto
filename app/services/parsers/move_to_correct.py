from datetime import datetime
from app.models import (Lot, Lot1, Lot2, Lot3, HistoricalLot, LotBase, LotHistoryAddons, LotOtherVehicle,
                        LotWithouImage, LotWithoutAuctionDate, LotOtherVehicleHistorical,
                        Lot4, Lot5, Lot6, Lot7)
from tortoise.transactions import in_transaction
from typing import List, Optional
from loguru import logger
from app.database import init_db, close_db
from app.services.lot_service import delete_lot

# Configuration for pagination
BATCH_SIZE = 100

async def fetch_lots_batch(offset: int, model: type[LotBase]) -> List[LotBase]:
    """Fetch a batch of data with pagination from specified model."""
    query = model.all().offset(offset).limit(BATCH_SIZE).prefetch_related(
        "vehicle_type",
        *model._meta.fk_fields,
        *model._meta.m2m_fields
    )
    return await query

async def should_move_to_historical(lot: LotBase) -> bool:
    """Determine if a lot should be moved to historical based on auction date."""
    if not lot.auction_date:
        return False
    return lot.auction_date < datetime.now().date()

async def get_target_model(lot: LotBase) -> Optional[type[LotBase]]:
    """Determine the target model for lot movement."""
    if not lot.auction_date:
        return LotWithoutAuctionDate
    elif should_move_to_historical(lot):
        if lot.vehicle_type.slug != 'automobile':
            return LotOtherVehicleHistorical
        else:
            return HistoricalLot
    elif lot.vehicle_type.slug != 'automobile':
        return LotOtherVehicle
    elif not lot.image_thubnail or len(lot.image_thubnail) < 5:
        return LotWithouImage
    return None

async def process_lot(lot: LotBase) -> bool:
    """Process a single lot: move to appropriate table and delete original."""
    try:
        target_model = await get_target_model(lot)
        if not target_model:
            return False
            
        logger.debug(f"Moving lot {lot.id} from {lot.__class__.__name__} to {target_model.__name__}")
        await lot.move_to(lot.id, target_model)
        await delete_lot(lot_id=lot.lot_id)
        return True
        
    except Exception as e:
        logger.error(f"Error processing lot {lot.id}: {str(e)}")
        return False

async def process_shard(model: type[LotBase]) -> tuple[int, int]:
    """Process all lots in a specific shard."""
    total_count = await model.all().count()
    processed_count = 0
    moved_count = 0
    
    for offset in range(0, total_count, BATCH_SIZE):
        logger.info(f"Processing batch {offset}-{offset+BATCH_SIZE-1} from {model.__name__}")
        lots = await fetch_lots_batch(offset, model)
        
        for lot in lots:
            processed_count += 1
            if await process_lot(lot):
                moved_count += 1
        
        logger.info(f"Progress for {model.__name__}: {processed_count}/{total_count} processed, {moved_count} moved")

    logger.success(f"Completed for {model.__name__}: {moved_count} lots moved")
    return processed_count, moved_count

async def mover():
    """Main processing function with transaction handling."""
    async with in_transaction():
        total_processed = 0
        total_moved = 0
        
        # Process main Lot table first
        processed, moved = await process_shard(Lot)
        total_processed += processed
        total_moved += moved
        
        # Process sharded tables
        shard_classes = [Lot1, Lot2, Lot3, Lot4, Lot5, Lot6, Lot7]
        for shard_class in shard_classes:
            processed, moved = await process_shard(shard_class)
            total_processed += processed
            total_moved += moved

        logger.success(f"Total completed: {total_moved} lots moved from {total_processed} processed")

async def main():
    logger.info('Starting historical lots migration process')
    await init_db()
    try:
        await mover()
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise
    finally:
        await close_db()
    logger.info('Migration completed')

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())