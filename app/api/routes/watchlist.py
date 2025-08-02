from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID
from app.models.user_watchlist import UserWatchlist
from app.schemas.watchlist import WatchlistEntrySchema
from app.models.lot import Lot
from app.schemas.lot import LotSchema
from app.api.dependencies import get_current_user  # Предполагается что есть
from tortoise.exceptions import IntegrityError

router = APIRouter()

MAX_WATCHLIST_SIZE = 100  # по желанию лимит

@router.post("/lots/{lot_id}/watch", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(lot_id: UUID, user=Depends(get_current_user)):
    # Проверка, что лот существует
    lot = await Lot.get_or_none(id=lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    count = await UserWatchlist.filter(user_id=user.id).count()
    if count >= MAX_WATCHLIST_SIZE:
        raise HTTPException(status_code=400, detail="Watchlist limit exceeded")

    # Попытка добавить, проверка уникальности через уникальный индекс
    try:
        entry = await UserWatchlist.create(user_id=user.id, lot_id=lot_id)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Lot already in watchlist")

    return {"message": "Lot added to watchlist"}

@router.delete("/lots/{lot_id}/watch", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(lot_id: UUID, user=Depends(get_current_user)):
    deleted = await UserWatchlist.filter(user_id=user.id, lot_id=lot_id).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="Lot not in watchlist")
    return

@router.get("/lots/watchlist", response_model=List[LotSchema])
async def get_watchlist(user=Depends(get_current_user)):
    entries = await UserWatchlist.filter(user_id=user.id).all()
    lot_ids = [entry.lot_id for entry in entries]
    lots = await Lot.filter(id__in=lot_ids)
    return [LotSchema.from_orm(lot) for lot in lots]
