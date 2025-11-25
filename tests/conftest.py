import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from tortoise.contrib.test import finalizer, initializer

from app.main import app
from app.models.user import User
from app.models.role import Role
from app.core.security.pass_hash import get_password_hash
from app.core.security.auth import create_access_token


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the entire test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function", autouse=True)
async def initialize_tests(request):
    """Initialize test database before each test"""
    db_url = "sqlite://:memory:"
    initializer(
        modules=["app.models.user", "app.models.role", "app.models.deposit",
                 "app.models.transaction", "app.models.notification",
                 "app.models.two_factor_auth"],
        db_url=db_url,
        app_label="models",
    )
    yield
    finalizer()


@pytest.fixture
async def client() -> AsyncGenerator:
    """Create async HTTP client for testing"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_user() -> User:
    """Create a test user"""
    user = await User.create(
        email="test@example.com",
        password_hash=get_password_hash("testpass123"),
        is_active=True,
        kyc_access=False,
        first_name="Test",
        last_name="User",
        balance=0.00
    )
    return user


@pytest.fixture
async def test_admin() -> User:
    """Create a test admin user"""
    admin = await User.create(
        email="admin@example.com",
        password_hash=get_password_hash("adminpass123"),
        is_active=True,
        kyc_access=True,
        balance=0.00
    )

    # Create admin role
    admin_role = await Role.create(
        name="admin",
        description="Administrator"
    )
    await admin.roles.add(admin_role)

    return admin


@pytest.fixture
async def user_token(test_user: User) -> str:
    """Generate JWT token for test user"""
    token_data = create_access_token(user_id=str(test_user.id))
    return token_data["access_token"]


@pytest.fixture
async def admin_token(test_admin: User) -> str:
    """Generate JWT token for admin user"""
    token_data = create_access_token(user_id=str(test_admin.id))
    return token_data["access_token"]
