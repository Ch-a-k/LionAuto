from fastapi import APIRouter, Query
# from app.tasks import create_lead_task
from app.schemas import CreateLeadSchema, LeadSchema
from typing import List, Optional
from app.services import lead_generation, get_leads, get_lead, update_lead, delete_lead, create_new_lead

router = APIRouter()

@router.post("/create_lead")
async def create_lead(
    body: CreateLeadSchema,
    local: Optional[str] = Query(None)
):
    # https://factumavto.amocrm.ru/
    # https://www.amocrm.ru/developers/content/crm_platform/users-api
    print(f'[DEBUG CREATE LEAD]: local: {local} body: {body}')
    lead = await create_new_lead(body)
    await lead_generation(body, local)
    return lead


@router.get("/leads/", response_model=List[LeadSchema])
async def read_leads(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = Query(None)
):
    return await get_leads(skip=skip, limit=limit, search=search)

@router.get("/leads/{lead_id}", response_model=LeadSchema)
async def read_lead(lead_id: int):
    return await get_lead(lead_id)

@router.put("/leads/{lead_id}", response_model=LeadSchema)
async def update_existing_lead(lead_id: int, lead: CreateLeadSchema):
    return await update_lead(lead_id, lead)

@router.delete("/leads/{lead_id}")
async def remove_lead(lead_id: int):
    await delete_lead(lead_id)
    return {"ok": True}