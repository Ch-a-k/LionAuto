import pytest
from decimal import Decimal
from httpx import AsyncClient

from app.models.user import User
from app.models.transaction import Transaction, TransactionType, TransactionStatus


@pytest.mark.asyncio
async def test_get_balance(client: AsyncClient, test_user: User, user_token: str):
    """Test getting user balance"""
    # Set initial balance
    test_user.balance = Decimal("5000.00")
    await test_user.save()

    response = await client.get(
        "/transactions/balance",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 5000.00
    assert data["currency"] == "USD"


@pytest.mark.asyncio
async def test_get_transactions(client: AsyncClient, test_user: User, user_token: str):
    """Test getting transaction history"""
    # Create test transactions
    await Transaction.create(
        user=test_user,
        transaction_type=TransactionType.deposit,
        amount=Decimal("1000.00"),
        status=TransactionStatus.completed,
        balance_before=Decimal("0.00"),
        balance_after=Decimal("1000.00"),
        description="Test deposit"
    )
    await Transaction.create(
        user=test_user,
        transaction_type=TransactionType.bid_hold,
        amount=Decimal("500.00"),
        status=TransactionStatus.completed,
        balance_before=Decimal("1000.00"),
        balance_after=Decimal("500.00"),
        description="Bid hold"
    )

    response = await client.get(
        "/transactions/",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["transactions"]) == 2


@pytest.mark.asyncio
async def test_get_transactions_filtered(client: AsyncClient, test_user: User, user_token: str):
    """Test filtering transactions by type"""
    await Transaction.create(
        user=test_user,
        transaction_type=TransactionType.deposit,
        amount=Decimal("1000.00"),
        status=TransactionStatus.completed,
        balance_before=Decimal("0.00"),
        balance_after=Decimal("1000.00")
    )
    await Transaction.create(
        user=test_user,
        transaction_type=TransactionType.withdrawal,
        amount=Decimal("500.00"),
        status=TransactionStatus.completed,
        balance_before=Decimal("1000.00"),
        balance_after=Decimal("500.00")
    )

    response = await client.get(
        "/transactions/?type=deposit",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["transactions"][0]["transaction_type"] == "deposit"


@pytest.mark.asyncio
async def test_get_transactions_pagination(client: AsyncClient, test_user: User, user_token: str):
    """Test transaction pagination"""
    # Create multiple transactions
    for i in range(25):
        await Transaction.create(
            user=test_user,
            transaction_type=TransactionType.deposit,
            amount=Decimal("100.00"),
            status=TransactionStatus.completed,
            balance_before=Decimal(str(i * 100)),
            balance_after=Decimal(str((i + 1) * 100))
        )

    # Get first page
    response = await client.get(
        "/transactions/?page=1&page_size=10",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 25
    assert len(data["transactions"]) == 10
    assert data["page"] == 1

    # Get second page
    response = await client.get(
        "/transactions/?page=2&page_size=10",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 10
    assert data["page"] == 2
