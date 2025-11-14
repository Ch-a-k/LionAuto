from fastapi import APIRouter, Depends
from app.models.translate import Translation
from tortoise.transactions import in_transaction
from app.models import Lot

router = APIRouter()


@router.get("/lot/{lot_id}")
async def get_translated_lot(lot_id: int, language: str = "ru"):
    ...