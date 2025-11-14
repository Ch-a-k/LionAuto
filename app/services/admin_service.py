from app.models import Lot, LotWithoutAuctionDate, HistoricalLot

async def get_count_lot(lot: bool = False, historical: bool = False):
    # Определяем модель в зависимости от флагов
    if lot:
        model = Lot
    elif historical:
        model = HistoricalLot
    else:
        model = LotWithoutAuctionDate
    
    # Проверяем, что модель была выбрана
    if model:
        # Используем Tortoise ORM для подсчета записей
        count = await model.all().count()  # all() возвращает все записи, count() подсчитывает их
        return count
    else:
        raise ValueError("Необходимо указать хотя бы один флаг: lot или historical.")