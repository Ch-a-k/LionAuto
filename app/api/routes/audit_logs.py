from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Body, Path, status
from pydantic import BaseModel, Field, field_validator
from tortoise.expressions import Q

from app.models.audit_log import CustomerAuditLog
from app.enums.audit_action import AuditAction
from app.models.customer import Customer  # предполагается, что модель существует

router = APIRouter()


# =======================
#        SCHEMAS
# =======================

class AuditLogCreate(BaseModel):
    customer_id: int | UUID = Field(..., description="ID клиента (int/UUID — под вашу модель Customer)")
    action: AuditAction = Field(..., description="Тип действия")
    details: Dict[str, Any] = Field(default_factory=dict, description="Произвольный JSON")

class AuditLogOut(BaseModel):
    id: int
    customer_id: int | UUID
    action: AuditAction
    details: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True

class AuditLogListOut(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[AuditLogOut]


# =======================
#      HELPERS
# =======================

async def _ensure_customer(customer_id: int | UUID) -> Customer:
    customer = await Customer.get_or_none(id=customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def _parse_sort(sort: Optional[str]) -> List[str]:
    """
    Принимает строки типа:
      - "-created_at" (по умолчанию)
      - "created_at"
      - "created_at,-id"
    Возвращает list для order_by.
    """
    if not sort:
        return ["-created_at"]
    fields = []
    for part in sort.split(","):
        part = part.strip()
        if not part:
            continue
        fields.append(part)
    return fields or ["-created_at"]


# =======================
#       ENDPOINTS
# =======================

@router.post("", response_model=AuditLogOut, status_code=status.HTTP_201_CREATED)
async def create_audit_log(payload: AuditLogCreate):
    """
    Сохранить новый audit-log.
    """
    await _ensure_customer(payload.customer_id)

    obj = await CustomerAuditLog.create(
        customer_id=payload.customer_id,
        action=payload.action,
        details=payload.details or {},
    )
    # Разворачиваем FK в поле customer_id
    return AuditLogOut(
        id=obj.id,
        customer_id=obj.customer_id,
        action=obj.action,
        details=obj.details,
        created_at=obj.created_at,
    )


@router.get("", response_model=AuditLogListOut)
async def list_audit_logs(
    # Фильтры
    customer_id: Optional[int | UUID] = Query(None, description="Фильтр по клиенту"),
    action: Optional[AuditAction] = Query(None, description="Фильтр по типу действия"),
    created_from: Optional[datetime] = Query(None, description="От даты/времени (UTC) включительно"),
    created_to: Optional[datetime] = Query(None, description="До даты/времени (UTC) включительно"),
    search: Optional[str] = Query(None, description="Поиск по details (JSON::text ILIKE)"),
    # Пагинация/сортировка
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort: Optional[str] = Query("-created_at", description="Поля сортировки, напр.: -created_at,created_at,-id"),
):
    """
    Список логов с фильтрами/пагинацией.
    """
    qs = CustomerAuditLog.all()

    if customer_id is not None:
        qs = qs.filter(customer_id=customer_id)

    if action is not None:
        qs = qs.filter(action=action)

    if created_from is not None:
        qs = qs.filter(created_at__gte=created_from)

    if created_to is not None:
        qs = qs.filter(created_at__lte=created_to)

    if search:
        # поиск по JSON как по тексту (работает для Postgres, где JSONB::text)
        # В Tortoise нет прямого ILIKE для JSON, используем сырой Q через __contains как упрощение (ключевое слово в сериализованном JSON).
        qs = qs.filter(details__contains=search)

    # total до ограничения
    total = await qs.count()

    # сортировка
    for f in _parse_sort(sort):
        qs = qs.order_by(f)

    rows = await qs.offset(offset).limit(limit).values(
        "id", "customer_id", "action", "details", "created_at"
    )

    items = [AuditLogOut(**r) for r in rows]
    return AuditLogListOut(total=total, limit=limit, offset=offset, items=items)


@router.get("/{log_id}", response_model=AuditLogOut)
async def get_audit_log(log_id: int = Path(..., ge=1)):
    """
    Получить один лог по id.
    """
    obj = await CustomerAuditLog.get_or_none(id=log_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Audit log not found")

    return AuditLogOut(
        id=obj.id,
        customer_id=obj.customer_id,
        action=obj.action,
        details=obj.details,
        created_at=obj.created_at,
    )


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audit_log(log_id: int = Path(..., ge=1)):
    """
    Удалить один лог по id.
    """
    deleted = await CustomerAuditLog.filter(id=log_id).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return None


# -------- Очистка --------

class ClearScope(BaseModel):
    scope: Literal["by_customer", "all"] = Field(..., description="Что чистим: by_customer или all")
    customer_id: Optional[int | UUID] = Field(None, description="Обязателен при scope=by_customer")

    @field_validator("customer_id")
    @classmethod
    def _customer_required_if_scope_by_customer(cls, v, info):
        data = info.data
        if data.get("scope") == "by_customer" and v is None:
            raise ValueError("customer_id is required when scope='by_customer'")
        return v


@router.post("/clear", status_code=status.HTTP_200_OK)
async def clear_audit_logs(body: ClearScope):
    """
    Очистить логи: либо по конкретному клиенту, либо все.
    Возвращает количество удалённых записей.
    """
    if body.scope == "by_customer":
        await _ensure_customer(body.customer_id)  # чтобы вернуть 404, если клиента нет
        deleted = await CustomerAuditLog.filter(customer_id=body.customer_id).delete()
        return {"deleted": deleted, "scope": "by_customer", "customer_id": str(body.customer_id)}
    else:
        deleted = await CustomerAuditLog.all().delete()
        return {"deleted": deleted, "scope": "all"}
