from tortoise.transactions import atomic
from app.models import Customer
from app.services.kyc.audit_service import AuditService

class CustomerService:
    @staticmethod
    @atomic()
    async def create_customer(user_id: int) -> Customer:
        customer = await Customer.create(user_id=user_id)
        await AuditService.log_status_change(customer.id, "pending")
        return customer