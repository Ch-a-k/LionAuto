# app/services/kyc/audit_service.py
from app.models.audit_log import CustomerAuditLog
from app.enums.audit_action import AuditAction

class AuditService:
    @staticmethod
    async def log_action(customer_id: int, action: AuditAction, details: dict):
        await CustomerAuditLog.create(
            customer_id=customer_id,
            action=action,
            details=details
        )

    @staticmethod
    async def log_status_change(customer_id: int, status: str):
        await AuditService.log_action(
            customer_id,
            AuditAction.STATUS_CHANGE,
            {"status": status}
        )