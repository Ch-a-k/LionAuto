from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID
from app.models.user_watchlist import UserWatchlist
from app.schemas.watchlist import WatchlistEntrySchema
from app.models.lot import Lot
from app.schemas.lot import VehicleModel
from app.api.dependencies import get_current_user
from tortoise.exceptions import IntegrityError

router = APIRouter()

MAX_WATCHLIST_SIZE = 100  # Максимальное количество лотов в списке избранного


@router.post("/lots/{lot_id}/watch", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(lot_id: UUID, user=Depends(get_current_user)):
    """
    Добавляет лот в список отслеживаемых (watchlist) текущего пользователя.

    Если лот уже присутствует в списке или превышен лимит избранного,
    выбрасывается исключение.  
    Проверяется существование лота и уникальность пары (user_id, lot_id).

    Args:
        lot_id (UUID): Уникальный идентификатор лота.
        user: Текущий авторизованный пользователь, полученный из зависимости get_current_user.

    Returns:
        dict: Сообщение об успешном добавлении лота в watchlist.

    Raises:
        HTTPException:
            404 — если лот не найден.
            400 — если превышен лимит в watchlist или лот уже добавлен ранее.
    """
    lot = await Lot.get_or_none(id=lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    count = await UserWatchlist.filter(user_id=user.id).count()
    if count >= MAX_WATCHLIST_SIZE:
        raise HTTPException(status_code=400, detail="Watchlist limit exceeded")

    try:
        entry = await UserWatchlist.create(user_id=user.id, lot_id=lot_id)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Lot already in watchlist")

    return {"message": "Lot added to watchlist"}


@router.delete("/lots/{lot_id}/watch", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(lot_id: UUID, user=Depends(get_current_user)):
    """
    Удаляет лот из списка отслеживаемых (watchlist) текущего пользователя.

    Args:
        lot_id (UUID): Уникальный идентификатор лота.
        user: Текущий авторизованный пользователь, полученный из зависимости get_current_user.

    Raises:
        HTTPException:
            404 — если лот отсутствует в списке отслеживаемых.
    """
    deleted = await UserWatchlist.filter(user_id=user.id, lot_id=lot_id).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="Lot not in watchlist")
    return


@router.get("/lots/watchlist", response_model=List[VehicleModel])
async def get_watchlist(user=Depends(get_current_user)):
    """
    Возвращает список всех лотов, добавленных пользователем в watchlist.

    Args:
        user: Текущий авторизованный пользователь, полученный из зависимости get_current_user.

    Returns:
        List[LotSchema]: Список объектов лотов, добавленных пользователем в избранное.

    Notes:
        - Возвращаемые лоты представлены в виде схемы LotSchema.
        - Порядок лотов не гарантируется (можно добавить сортировку при необходимости).
    """
    entries = await UserWatchlist.filter(user_id=user.id).all()
    lot_ids = [entry.lot_id for entry in entries]
    lots = await Lot.filter(id__in=lot_ids)
    return [VehicleModel.from_orm(lot) for lot in lots]
