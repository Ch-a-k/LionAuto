from app.models import Lot, Lot1, Lot2, Lot3, Lot4, Lot5, Lot6, Lot7
from loguru import logger
from app.database import init_db, close_db
from tortoise.transactions import in_transaction
import asyncio

async def migrate_lots_to_shards(batch_size: int = 1000) -> dict:
    """
    Переносит данные из основной таблицы Lot в шарды (Lot1-Lot7)
    Возвращает статистику по перенесенным записям
    """
    stats = {
        'total_lots': 0,
        'migrated': 0,
        'errors': 0,
        'shards': {f'Lot{i}': 0 for i in range(1, 8)}
    }

    stats['total_lots'] = await Lot.all().count()
    if stats['total_lots'] == 0:
        return stats

    logger.info(f"Starting migration of {stats['total_lots']} lots to shards...")

    last_id = 0
    has_more = True

    while has_more:
        lots = await Lot.filter(id__gt=last_id).order_by('id').limit(batch_size)
        if not lots:
            has_more = False
            break

        last_id = lots[-1].id

        for lot in lots:
            await handle_lot(lot, stats)

    logger.success(f"Migration completed. Stats: {stats}")
    return stats

async def handle_lot(lot, stats, attempt=1, max_attempts=3):
    try:
        shard_num = (lot.id % 10_000_000) % 7 + 1
        shard_class = {
            1: Lot1, 2: Lot2, 3: Lot3, 4: Lot4, 5: Lot5, 6: Lot6, 7: Lot7
        }[shard_num]

        if await shard_class.filter(id=lot.id).exists():
            logger.warning(f"Lot {lot.id} already exists in {shard_class.__name__}")
            stats['errors'] += 1
            return

        lot_data = {}
        for field_name in lot._meta.fields_map.keys():
            if field_name == 'id':
                continue

            if field_name in lot._meta.fk_fields:
                related = getattr(lot, field_name)
                if related:
                    lot_data[field_name] = await related
            elif field_name in lot._meta.m2m_fields:
                continue
            else:
                lot_data[field_name] = getattr(lot, field_name)

        async with in_transaction() as conn:
            new_lot = shard_class(id=lot.id, **lot_data)
            await new_lot.save(using_db=conn)

            # M2M связи переносятся отдельно
            for field_name in lot._meta.m2m_fields:
                m2m_values = await getattr(lot, field_name).all()
                if m2m_values:
                    m2m_field = getattr(new_lot, field_name)
                    await m2m_field.add(*m2m_values, using_db=conn)

            await lot.delete(using_db=conn)

        stats['migrated'] += 1
        stats['shards'][shard_class.__name__] += 1

        if stats['migrated'] % 100 == 0:
            logger.info(f"Migrated {stats['migrated']} lots so far...")

    except Exception as e:
        if "deadlock detected" in str(e).lower() and attempt < max_attempts:
            logger.warning(f"Deadlock while migrating lot {lot.id}, retrying (attempt {attempt + 1})...")
            await asyncio.sleep(0.5)
            return await handle_lot(lot, stats, attempt + 1)
        logger.error(f"Error migrating lot {lot.id}: {str(e)}")
        stats['errors'] += 1

async def main():
    logger.info('Starting data migration process')
    await init_db()
    try:
        await migrate_lots_to_shards()
    finally:
        await close_db()
    logger.info('Migration completed')

if __name__ == "__main__":
    asyncio.run(main())