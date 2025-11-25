import pytest
from decimal import Decimal

from app.models.user import User
from app.models.deposit import Deposit, DepositStatus
from app.models.transaction import Transaction, TransactionType
from app.models.notification import Notification, NotificationType
from app.services.deposit_service import DepositService
from app.services.transaction_service import TransactionService
from app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_deposit_approval_creates_transaction(test_user: User):
    """Test that approving a deposit creates a transaction"""
    # Create deposit
    deposit = await Deposit.create(
        user=test_user,
        amount=Decimal("1000.00"),
        payment_method="bank_transfer",
        status=DepositStatus.pending
    )

    initial_balance = test_user.balance

    # Approve deposit
    approved_deposit = await DepositService.approve_deposit(
        deposit_id=deposit.id,
        transaction_id="TXN123"
    )

    assert approved_deposit.status == DepositStatus.completed

    # Verify balance updated
    await test_user.refresh_from_db()
    assert test_user.balance == initial_balance + Decimal("1000.00")

    # Verify transaction created
    transaction = await Transaction.get_or_none(deposit_id=deposit.id)
    assert transaction is not None
    assert transaction.transaction_type == TransactionType.deposit
    assert transaction.amount == Decimal("1000.00")
    assert transaction.balance_after == test_user.balance


@pytest.mark.asyncio
async def test_deposit_approval_sends_notification(test_user: User):
    """Test that approving a deposit sends notification"""
    deposit = await Deposit.create(
        user=test_user,
        amount=Decimal("1000.00"),
        payment_method="bank_transfer",
        status=DepositStatus.pending
    )

    # Approve deposit
    await DepositService.approve_deposit(deposit_id=deposit.id)

    # Verify notification created
    notification = await Notification.get_or_none(
        user=test_user,
        notification_type=NotificationType.deposit_received
    )
    assert notification is not None
    assert "approved" in notification.message.lower()


@pytest.mark.asyncio
async def test_reject_deposit_sends_notification(test_user: User):
    """Test that rejecting a deposit sends notification"""
    deposit = await Deposit.create(
        user=test_user,
        amount=Decimal("1000.00"),
        payment_method="bank_transfer",
        status=DepositStatus.pending
    )

    initial_balance = test_user.balance

    # Reject deposit
    await DepositService.reject_deposit(
        deposit_id=deposit.id,
        admin_notes="Invalid reference"
    )

    # Verify balance unchanged
    await test_user.refresh_from_db()
    assert test_user.balance == initial_balance

    # Verify notification created
    notification = await Notification.get_or_none(
        user=test_user,
        notification_type=NotificationType.deposit_failed
    )
    assert notification is not None


@pytest.mark.asyncio
async def test_transaction_service_balance_check(test_user: User):
    """Test transaction service balance checking"""
    test_user.balance = Decimal("100.00")
    await test_user.save()

    balance = await TransactionService.get_user_balance(test_user.id)
    assert balance == Decimal("100.00")


@pytest.mark.asyncio
async def test_refund_updates_balance(test_user: User):
    """Test that refund updates user balance"""
    test_user.balance = Decimal("1000.00")
    await test_user.save()

    initial_balance = test_user.balance

    # Process refund
    transaction = await TransactionService.refund_amount(
        user=test_user,
        amount=Decimal("500.00"),
        description="Test refund"
    )

    assert transaction.transaction_type == TransactionType.refund
    assert transaction.amount == Decimal("500.00")

    # Verify balance updated
    await test_user.refresh_from_db()
    assert test_user.balance == initial_balance + Decimal("500.00")


@pytest.mark.asyncio
async def test_notification_service_creates_notification(test_user: User):
    """Test notification service creates notification"""
    notification = await NotificationService.create_notification(
        user=test_user,
        notification_type=NotificationType.info,
        title="Test Notification",
        message="Test message"
    )

    assert notification.user_id == test_user.id
    assert notification.title == "Test Notification"
    assert notification.is_read is False


@pytest.mark.asyncio
async def test_mark_all_notifications_as_read(test_user: User):
    """Test marking all notifications as read"""
    # Create multiple notifications
    for i in range(5):
        await Notification.create(
            user=test_user,
            notification_type=NotificationType.info,
            title=f"Test {i}",
            message=f"Message {i}",
            is_read=False
        )

    # Mark all as read
    count = await NotificationService.mark_all_as_read(test_user.id)
    assert count == 5

    # Verify all marked as read
    unread = await Notification.filter(user=test_user, is_read=False).count()
    assert unread == 0


@pytest.mark.asyncio
async def test_get_user_transactions_pagination(test_user: User):
    """Test transaction service pagination"""
    # Create 15 transactions
    for i in range(15):
        await Transaction.create(
            user=test_user,
            transaction_type=TransactionType.deposit,
            amount=Decimal("100.00"),
            status="completed",
            balance_before=Decimal(str(i * 100)),
            balance_after=Decimal(str((i + 1) * 100))
        )

    # Get first page
    transactions, total = await TransactionService.get_user_transactions(
        user_id=test_user.id,
        page=1,
        page_size=10
    )

    assert total == 15
    assert len(transactions) == 10

    # Get second page
    transactions, total = await TransactionService.get_user_transactions(
        user_id=test_user.id,
        page=2,
        page_size=10
    )

    assert total == 15
    assert len(transactions) == 5


@pytest.mark.asyncio
async def test_deposit_amount_validation():
    """Test that deposit amount must be positive"""
    from pydantic import ValidationError
    from app.schemas.deposit import DepositCreate

    with pytest.raises(ValidationError):
        DepositCreate(
            amount=-100.00,
            payment_method="bank_transfer"
        )


@pytest.mark.asyncio
async def test_create_deposit_with_notification(test_user: User):
    """Test creating deposit sends notification"""
    deposit = await DepositService.create_deposit(
        user=test_user,
        amount=Decimal("1000.00"),
        payment_method="bank_transfer",
        description="Test deposit"
    )

    assert deposit.status == DepositStatus.pending

    # Verify notification created
    notification = await Notification.get_or_none(
        user=test_user,
        notification_type=NotificationType.info
    )
    assert notification is not None
    assert "deposit request" in notification.message.lower()
