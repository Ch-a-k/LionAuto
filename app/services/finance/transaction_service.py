from uuid import UUID
from decimal import Decimal
from typing import Optional
from tortoise.transactions import in_transaction

from app.models.user import User
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.bid import Bid


class TransactionService:
    @staticmethod
    async def get_user_transactions(
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        transaction_type: Optional[TransactionType] = None
    ) -> tuple[list[Transaction], int]:
        """Get user transactions with pagination"""
        query = Transaction.filter(user_id=user_id)

        if transaction_type:
            query = query.filter(transaction_type=transaction_type)

        total = await query.count()
        transactions = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)

        return transactions, total

    @staticmethod
    async def hold_bid_amount(user: User, bid: Bid, amount: Decimal) -> Transaction:
        """Hold amount for a bid"""
        async with in_transaction():
            if user.balance < amount:
                raise ValueError("Insufficient balance")

            balance_before = user.balance
            user.balance -= amount
            await user.save()

            transaction = await Transaction.create(
                user=user,
                transaction_type=TransactionType.bid_hold,
                amount=amount,
                status=TransactionStatus.completed,
                balance_before=balance_before,
                balance_after=user.balance,
                bid=bid,
                description=f"Hold for bid on lot {bid.lot_id}"
            )

            return transaction

    @staticmethod
    async def release_bid_amount(user: User, bid: Bid, amount: Decimal) -> Transaction:
        """Release held amount from a bid"""
        async with in_transaction():
            balance_before = user.balance
            user.balance += amount
            await user.save()

            transaction = await Transaction.create(
                user=user,
                transaction_type=TransactionType.bid_release,
                amount=amount,
                status=TransactionStatus.completed,
                balance_before=balance_before,
                balance_after=user.balance,
                bid=bid,
                description=f"Release hold for bid on lot {bid.lot_id}"
            )

            return transaction

    @staticmethod
    async def deduct_bid_amount(user: User, bid: Bid, amount: Decimal) -> Transaction:
        """Deduct amount for a won bid (already held)"""
        transaction = await Transaction.create(
            user=user,
            transaction_type=TransactionType.bid_deduction,
            amount=amount,
            status=TransactionStatus.completed,
            balance_before=user.balance,
            balance_after=user.balance,  # Already deducted during hold
            bid=bid,
            description=f"Payment for won bid on lot {bid.lot_id}"
        )

        return transaction

    @staticmethod
    async def refund_amount(user: User, amount: Decimal, description: str) -> Transaction:
        """Refund amount to user"""
        async with in_transaction():
            balance_before = user.balance
            user.balance += amount
            await user.save()

            transaction = await Transaction.create(
                user=user,
                transaction_type=TransactionType.refund,
                amount=amount,
                status=TransactionStatus.completed,
                balance_before=balance_before,
                balance_after=user.balance,
                description=description
            )

            return transaction

    @staticmethod
    async def get_user_balance(user_id: UUID) -> Decimal:
        """Get current user balance"""
        user = await User.get(id=user_id)
        return user.balance
