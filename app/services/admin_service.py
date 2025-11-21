from app.models import Lot, LotWithoutAuctionDate, HistoricalLot


async def get_count_lot(lot: bool = False, historical: bool = False) -> int:
    """
    Возвращает количество лотов:
      - lot=True        → все актуальные лоты по ВСЕМ шардам Lot1..Lot7
      - historical=True → все исторические лоты (HistoricalLot)
      - иначе           → лоты без даты аукциона (LotWithoutAuctionDate)
    """
    # Если оба флага выставлены – считаем это ошибкой, чтобы не путаться
    if lot and historical:
        raise ValueError("Нельзя одновременно указывать lot=True и historical=True")

    if lot:
        # ✅ все шардированные Lot1..Lot7
        count = await Lot.count_across_shards()
        return count

    if historical:
        # ✅ вся таблица HistoricalLot (без шардов)
        count = await HistoricalLot.historical_count()
        return count

    # по умолчанию – LotWithoutAuctionDate (у него шардинга нет)
    count = await LotWithoutAuctionDate.all().count()
    return count
