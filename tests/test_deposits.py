import pytest
from decimal import Decimal
from httpx import AsyncClient

from app.models.user import User
from app.models.deposit import Deposit, DepositStatus


@pytest.mark.asyncio
async def test_create_deposit(client: AsyncClient, test_user: User, user_token: str):
    """Test creating a deposit request"""
    deposit_data = {
        "amount": 1000.00,
        "payment_method": "bank_transfer",
        "payment_reference": "REF123456",
        "description": "Test deposit"
    }

    response = await client.post(
        "/deposits/",
        headers={"Authorization": f"Bearer {user_token}"},
        json=deposit_data
    )

    assert response.status_code == 201
    data = response.json()
    assert float(data["amount"]) == 1000.00
    assert data["status"] == "pending"
    assert data["payment_method"] == "bank_transfer"
    assert data["payment_reference"] == "REF123456"

    # Verify in database
    deposit = await Deposit.get(id=data["id"])
    assert deposit.status == DepositStatus.pending
    assert deposit.user_id == test_user.id


@pytest.mark.asyncio
async def test_create_deposit_invalid_amount(client: AsyncClient, test_user: User, user_token: str):
    """Test creating deposit with invalid amount"""
    deposit_data = {
        "amount": -100.00,  # Negative amount
        "payment_method": "bank_transfer"
    }

    response = await client.post(
        "/deposits/",
        headers={"Authorization": f"Bearer {user_token}"},
        json=deposit_data
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_deposits(client: AsyncClient, test_user: User, user_token: str):
    """Test getting user deposits"""
    # Create test deposits
    await Deposit.create(
        user=test_user,
        amount=Decimal("1000.00"),
        payment_method="bank_transfer",
        status=DepositStatus.pending
    )
    await Deposit.create(
        user=test_user,
        amount=Decimal("2000.00"),
        payment_method="credit_card",
        status=DepositStatus.completed
    )

    response = await client.get(
        "/deposits/",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["deposits"]) == 2


@pytest.mark.asyncio
async def test_get_deposits_filtered(client: AsyncClient, test_user: User, user_token: str):
    """Test filtering deposits by status"""
    await Deposit.create(
        user=test_user,
        amount=Decimal("1000.00"),
        payment_method="bank_transfer",
        status=DepositStatus.pending
    )
    await Deposit.create(
        user=test_user,
        amount=Decimal("2000.00"),
        payment_method="credit_card",
        status=DepositStatus.completed
    )

    response = await client.get(
        "/deposits/?status=pending",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["deposits"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_approve_deposit(client: AsyncClient, test_user: User, admin_token: str):
    """Test approving a deposit (admin only)"""
    # Create pending deposit
    deposit = await Deposit.create(
        user=test_user,
        amount=Decimal("1000.00"),
        payment_method="bank_transfer",
        status=DepositStatus.pending
    )

    initial_balance = test_user.balance

    response = await client.put(
        f"/deposits/{deposit.id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "transaction_id": "TXN123456",
            "admin_notes": "Verified and approved"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["transaction_id"] == "TXN123456"

    # Verify balance updated
    await test_user.refresh_from_db()
    assert test_user.balance == initial_balance + Decimal("1000.00")

    # Verify transaction created
    from app.models.transaction import Transaction
    transaction = await Transaction.get_or_none(deposit_id=deposit.id)
    assert transaction is not None
    assert transaction.transaction_type == "deposit"


@pytest.mark.asyncio
async def test_reject_deposit(client: AsyncClient, test_user: User, admin_token: str):
    """Test rejecting a deposit"""
    deposit = await Deposit.create(
        user=test_user,
        amount=Decimal("1000.00"),
        payment_method="bank_transfer",
        status=DepositStatus.pending
    )

    initial_balance = test_user.balance

    response = await client.put(
        f"/deposits/{deposit.id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"admin_notes": "Invalid reference"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"

    # Verify balance unchanged
    await test_user.refresh_from_db()
    assert test_user.balance == initial_balance


@pytest.mark.asyncio
async def test_approve_deposit_non_admin(client: AsyncClient, test_user: User, user_token: str):
    """Test that non-admin cannot approve deposits"""
    deposit = await Deposit.create(
        user=test_user,
        amount=Decimal("1000.00"),
        payment_method="bank_transfer",
        status=DepositStatus.pending
    )

    response = await client.put(
        f"/deposits/{deposit.id}/approve",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"transaction_id": "TXN123"}
    )

    assert response.status_code == 403  # Forbidden
