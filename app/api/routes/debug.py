# app/api/routes/debug.py
from fastapi import APIRouter
import httpx

router = APIRouter(prefix="/_debug", tags=["_debug"])

@router.get("/cdp")
async def cdp_info():
    url = "http://127.0.0.1:9222/json/version"
    try:
        async with httpx.AsyncClient(timeout=1.5) as c:
            r = await c.get(url)
            return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}
