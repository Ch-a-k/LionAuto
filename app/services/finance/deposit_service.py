from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional
from tortoise.transactions import in_transaction

from app.models.user import User
from app.models.deposit import Deposit, DepositStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.services.communication.notification_service import NotificationService
from app.models.notification import NotificationType


class DepositService:
    @staticmethod
    async def create_deposit(
        user: User,
        amount: Decimal,
        payment_method: str,
        payment_reference: Optional[str] = None,
        description: Optional[str] = None
    ) -> Deposit:
        """Create a new deposit request"""
        deposit = await Deposit.create(
            user=user,
            amount=amount,
            payment_method=payment_method,
            payment_reference=payment_reference,
            description=description,
            status=DepositStatus.pending
        )

        # Send notification
        await NotificationService.create_notification(
            user=user,
            notification_type=NotificationType.info,
            title="Deposit Request Created",
            message=f"Your deposit request for ${amount} has been created and is pending approval.",
            related_deposit=deposit
        )

        return deposit

    @staticmethod
    async def approve_deposit(deposit_id: UUID, transaction_id: Optional[str] = None, admin_notes: Optional[str] = None) -> Deposit:
        """Approve a deposit and credit user balance"""
        async with in_transaction():
            deposit = await Deposit.get(id=deposit_id).prefetch_related("user")

            if deposit.status != DepositStatus.pending:
                raise ValueError(f"Deposit is not pending, current status: {deposit.status}")

            user = deposit.user
            balance_before = user.balance

            # Update user balance
            user.balance += deposit.amount
            await user.save()

            # Update deposit status
            deposit.status = DepositStatus.completed
            deposit.transaction_id = transaction_id
            deposit.admin_notes = admin_notes
            deposit.completed_at = datetime.utcnow()
            await deposit.save()

            # Create transaction record
            await Transaction.create(
                user=user,
                transaction_type=TransactionType.deposit,
                amount=deposit.amount,
                status=TransactionStatus.completed,
                balance_before=balance_before,
                balance_after=user.balance,
                deposit=deposit,
                description=f"Deposit approved: {deposit.payment_reference or deposit.id}"
            )

            # Send notification
            await NotificationService.create_notification(
                user=user,
                notification_type=NotificationType.deposit_received,
                title="Deposit Approved",
                message=f"Your deposit of ${deposit.amount} has been approved and added to your balance.",
                related_deposit=deposit
            )

            return deposit

    @staticmethod
    async def reject_deposit(deposit_id: UUID, admin_notes: Optional[str] = None) -> Deposit:
        """Reject a deposit"""
        deposit = await Deposit.get(id=deposit_id).prefetch_related("user")

        if deposit.status != DepositStatus.pending:
            raise ValueError(f"Deposit is not pending, current status: {deposit.status}")

        deposit.status = DepositStatus.failed
        deposit.admin_notes = admin_notes
        await deposit.save()

        # Send notification
        await NotificationService.create_notification(
            user=deposit.user,
            notification_type=NotificationType.deposit_failed,
            title="Deposit Rejected",
            message=f"Your deposit of ${deposit.amount} has been rejected. {admin_notes or ''}",
            related_deposit=deposit
        )

        return deposit

    @staticmethod
    async def get_user_deposits(
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[DepositStatus] = None
    ) -> tuple[list[Deposit], int]:
        """Get user deposits with pagination"""
        query = Deposit.filter(user_id=user_id)

        if status:
            query = query.filter(status=status)

        total = await query.count()
        deposits = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)

        return deposits, total
