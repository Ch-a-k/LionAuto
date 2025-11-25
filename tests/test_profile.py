import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_get_profile(client: AsyncClient, test_user: User, user_token: str):
    """Test getting user profile"""
    response = await client.get(
        "/profile/me",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["first_name"] == "Test"
    assert data["last_name"] == "User"
    assert data["balance"] == 0.00
    assert data["two_fa_enabled"] is False


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, test_user: User, user_token: str):
    """Test updating user profile"""
    update_data = {
        "first_name": "John",
        "last_name": "Doe",
        "country": "USA",
        "phone": "+1234567890",
        "tg_username": "@johndoe"
    }

    response = await client.put(
        "/profile/me",
        headers={"Authorization": f"Bearer {user_token}"},
        json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["country"] == "USA"
    assert data["phone"] == "+1234567890"
    assert data["tg_username"] == "@johndoe"

    # Verify in database
    user = await User.get(id=test_user.id)
    assert user.first_name == "John"
    assert user.last_name == "Doe"


@pytest.mark.asyncio
async def test_update_profile_partial(client: AsyncClient, test_user: User, user_token: str):
    """Test partial profile update"""
    response = await client.put(
        "/profile/me",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"country": "Canada"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["country"] == "Canada"
    # Other fields should remain unchanged
    assert data["first_name"] == "Test"
    assert data["last_name"] == "User"


@pytest.mark.asyncio
async def test_get_profile_unauthorized(client: AsyncClient):
    """Test getting profile without authentication"""
    response = await client.get("/profile/me")
    assert response.status_code == 401
