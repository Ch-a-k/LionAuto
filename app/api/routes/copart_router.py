# app/api/routes/copart_router.py
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, AnyUrl
from typing import Optional, Dict, Any
from loguru import logger
from app.services.copart_controller import CopartController

router = APIRouter()

def get_copart_ctrl() -> CopartController:
    """
    Достаём контроллер из app.state.
    Подключать как Depends во всех хэндлерах этого роутера.
    """
    from app.main import app  # импорт лишь для доступа к state
    ctrl: Optional[CopartController] = getattr(app.state, "copart_controller", None)
    if not ctrl:
        raise HTTPException(status_code=503, detail="Copart controller is not initialized")
    return ctrl

@router.get("/status")
async def bot_status(ctrl: CopartController = Depends(get_copart_ctrl)) -> Dict[str, Any]:
    """Текущий статус бота (запущен/здоров/логин)."""
    return await ctrl.status()

@router.post("/start")
async def bot_start(ctrl: CopartController = Depends(get_copart_ctrl)):
    """Запускает бота, если он ещё не запущен."""
    await ctrl.start()
    return {"ok": True}

@router.post("/stop")
async def bot_stop(ctrl: CopartController = Depends(get_copart_ctrl)):
    """Останавливает бота, если он запущен."""
    await ctrl.stop()
    return {"ok": True}

class JoinRequest(BaseModel):
    title_like: str

@router.post("/join")
async def bot_join(req: JoinRequest, ctrl: CopartController = Depends(get_copart_ctrl)):
    """
    Join в live-аукцион по части названия (как на календаре Copart).
    """
    ok = await ctrl.join_live(req.title_like)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to join live auction")
    return {"joined": True}

class BidRequest(BaseModel):
    amount: Optional[str | int] = None
    times: int = 1
    spacing_sec: float = 0.35

@router.post("/bid")
async def bot_bid(req: BidRequest, ctrl: CopartController = Depends(get_copart_ctrl)):
    """
    Сделать ставку. Если amount не задан — кликнуть дефолтную кнопку Bid.
    """
    ok = await ctrl.bid(amount=req.amount, times=req.times, spacing_sec=req.spacing_sec)
    if not ok:
        raise HTTPException(status_code=400, detail="Bid failed")
    return {"bid": True}

class LotDetailsRequest(BaseModel):
    url: AnyUrl

@router.post("/lot-details")
async def bot_lot_details(req: LotDetailsRequest, ctrl: CopartController = Depends(get_copart_ctrl)):
    """
    Собрать детали лота по ссылке.
    """
    details = await ctrl.lot_details(str(req.url))
    return details

@router.post("/ensure-session")
async def bot_ensure_session(ctrl: CopartController = Depends(get_copart_ctrl)):
    """Ручная ensure_session()."""
    ok = await ctrl.ensure_session()
    return {"ok": ok}

@router.get("/health")
async def bot_health(ctrl: CopartController = Depends(get_copart_ctrl)):
    """Быстрый пинг дашборда."""
    return {"healthy": await ctrl.health()}
