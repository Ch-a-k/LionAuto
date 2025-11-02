from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.models.bot_session import BotSession
from app.schemas.bot_session import (
    BotSessionIn, BotSessionOut, BotSessionListOut, BotSessionUpdate
)

router = APIRouter(prefix="/botsessions", tags=["Bot Sessions"])


# ---------- Create (409 if exists) ----------
@router.post("", response_model=BotSessionOut, status_code=201)
async def create_session(payload: BotSessionIn):
    exists = await BotSession.filter(username=payload.username).exists()
    if exists:
        raise HTTPException(status_code=409, detail="Session already exists for this username")
    obj = await BotSession.create(
        username=payload.username,
        storage_state_json=payload.storage_state_json,
    )
    return BotSessionOut(
        username=obj.username,
        storage_state_json=obj.storage_state_json,
        updated_at=obj.updated_at,
    )


# ---------- Upsert (PUT) ----------
@router.put("/{username}", response_model=BotSessionOut)
async def upsert_session(username: str, payload: BotSessionUpdate):
    async with in_transaction():
        obj = await BotSession.get_or_none(username=username)
        if obj:
            obj.storage_state_json = payload.storage_state_json
            await obj.save()  # updated_at auto_now
        else:
            obj = await BotSession.create(
                username=username,
                storage_state_json=payload.storage_state_json,
            )
    return BotSessionOut(
        username=obj.username,
        storage_state_json=obj.storage_state_json,
        updated_at=obj.updated_at,
    )


# ---------- Partial update (PATCH) ----------
@router.patch("/{username}", response_model=BotSessionOut)
async def update_session(username: str, payload: BotSessionUpdate):
    obj = await BotSession.get_or_none(username=username)
    if not obj:
        raise HTTPException(status_code=404, detail="Session not found")
    obj.storage_state_json = payload.storage_state_json
    await obj.save()
    return BotSessionOut(
        username=obj.username,
        storage_state_json=obj.storage_state_json,
        updated_at=obj.updated_at,
    )


# ---------- Get one ----------
@router.get("/{username}", response_model=BotSessionOut)
async def get_session(username: str):
    obj = await BotSession.get_or_none(username=username)
    if not obj:
        raise HTTPException(status_code=404, detail="Session not found")
    return BotSessionOut(
        username=obj.username,
        storage_state_json=obj.storage_state_json,
        updated_at=obj.updated_at,
    )


# ---------- List (поиск и пагинация) ----------
@router.get("", response_model=BotSessionListOut)
async def list_sessions(
    q: Optional[str] = Query(None, description="Поиск по username (contains, case-insensitive)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order: str = Query("-updated_at", pattern="^-?(username|updated_at)$")
):
    qs = BotSession.all()
    if q:
        qs = qs.filter(Q(username__icontains=q))

    # сортировка
    if order.startswith("-"):
        qs = qs.order_by(order)
    else:
        qs = qs.order_by(order)

    total = await qs.count()
    rows = await qs.limit(limit).offset(offset)
    items = [
        BotSessionOut(username=r.username, storage_state_json=r.storage_state_json, updated_at=r.updated_at)
        for r in rows
    ]
    return BotSessionListOut(items=items, total=total, limit=limit, offset=offset)


# ---------- Delete one ----------
@router.delete("/{username}", status_code=204)
async def delete_session(username: str):
    deleted = await BotSession.filter(username=username).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return None


# ---------- Clear all (подтверждение) ----------
@router.delete("", status_code=204)
async def clear_all(confirm: bool = Query(False, description="Нужно явно confirm=true")):
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass confirm=true to delete all sessions")
    await BotSession.all().delete()
    return None
