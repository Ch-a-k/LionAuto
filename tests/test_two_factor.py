import pytest
import pyotp
from httpx import AsyncClient

from app.models.user import User
from app.models.two_factor_auth import TwoFactorBackupCode


@pytest.mark.asyncio
async def test_enable_2fa(client: AsyncClient, test_user: User, user_token: str):
    """Test enabling 2FA"""
    response = await client.post(
        "/2fa/enable",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "secret" in data
    assert "qr_code_url" in data
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 10
    assert data["qr_code_url"].startswith("data:image/png;base64,")

    # Verify secret stored
    await test_user.refresh_from_db()
    assert test_user.two_fa_secret is not None
    assert test_user.two_fa_enabled is False  # Not yet activated


@pytest.mark.asyncio
async def test_enable_2fa_already_enabled(client: AsyncClient, test_user: User, user_token: str):
    """Test enabling 2FA when already enabled"""
    test_user.two_fa_enabled = True
    test_user.two_fa_secret = "TEST_SECRET"
    await test_user.save()

    response = await client.post(
        "/2fa/enable",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 400
    assert "already enabled" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_and_activate_2fa(client: AsyncClient, test_user: User, user_token: str):
    """Test verifying and activating 2FA"""
    # First enable 2FA to get secret
    enable_response = await client.post(
        "/2fa/enable",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    secret = enable_response.json()["secret"]

    # Generate valid TOTP code
    totp = pyotp.TOTP(secret)
    code = totp.now()

    # Verify and activate
    response = await client.post(
        "/2fa/verify",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"code": code}
    )

    assert response.status_code == 200

    # Verify 2FA is now enabled
    await test_user.refresh_from_db()
    assert test_user.two_fa_enabled is True


@pytest.mark.asyncio
async def test_verify_2fa_invalid_code(client: AsyncClient, test_user: User, user_token: str):
    """Test verifying 2FA with invalid code"""
    # Enable 2FA
    await client.post(
        "/2fa/enable",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    # Try to verify with invalid code
    response = await client.post(
        "/2fa/verify",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"code": "000000"}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_2fa_status(client: AsyncClient, test_user: User, user_token: str):
    """Test getting 2FA status"""
    response = await client.get(
        "/2fa/status",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["two_fa_enabled"] is False
    assert data["backup_codes_count"] == 0


@pytest.mark.asyncio
async def test_get_2fa_status_enabled(client: AsyncClient, test_user: User, user_token: str):
    """Test getting 2FA status when enabled"""
    # Enable and activate 2FA
    test_user.two_fa_enabled = True
    test_user.two_fa_secret = "TEST_SECRET"
    await test_user.save()

    # Create backup codes
    for i in range(5):
        await TwoFactorBackupCode.create(
            user=test_user,
            code=f"CODE{i:04d}-{i:04d}-{i:04d}-{i:04d}"
        )

    response = await client.get(
        "/2fa/status",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["two_fa_enabled"] is True
    assert data["backup_codes_count"] == 5


@pytest.mark.asyncio
async def test_disable_2fa(client: AsyncClient, test_user: User, user_token: str):
    """Test disabling 2FA"""
    # Setup: Enable 2FA
    secret = pyotp.random_base32()
    test_user.two_fa_enabled = True
    test_user.two_fa_secret = secret
    await test_user.save()

    # Create backup codes
    await TwoFactorBackupCode.create(
        user=test_user,
        code="TEST-CODE-1234-5678"
    )

    # Generate valid code
    totp = pyotp.TOTP(secret)
    code = totp.now()

    # Disable 2FA
    response = await client.post(
        "/2fa/disable",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "code": code,
            "password": "testpass123"
        }
    )

    assert response.status_code == 200

    # Verify 2FA is disabled
    await test_user.refresh_from_db()
    assert test_user.two_fa_enabled is False
    assert test_user.two_fa_secret is None

    # Verify backup codes deleted
    backup_codes_count = await TwoFactorBackupCode.filter(user=test_user).count()
    assert backup_codes_count == 0


@pytest.mark.asyncio
async def test_disable_2fa_wrong_password(client: AsyncClient, test_user: User, user_token: str):
    """Test disabling 2FA with wrong password"""
    # Setup: Enable 2FA
    secret = pyotp.random_base32()
    test_user.two_fa_enabled = True
    test_user.two_fa_secret = secret
    await test_user.save()

    totp = pyotp.TOTP(secret)
    code = totp.now()

    response = await client.post(
        "/2fa/disable",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "code": code,
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_backup_code_usage(client: AsyncClient, test_user: User):
    """Test using backup code for login"""
    from app.services.two_factor_service import TwoFactorService

    # Setup 2FA
    test_user.two_fa_enabled = True
    test_user.two_fa_secret = pyotp.random_base32()
    await test_user.save()

    backup_code = "TEST-1234-5678-9012"
    await TwoFactorBackupCode.create(
        user=test_user,
        code=backup_code
    )

    # Verify backup code works
    result = await TwoFactorService.verify_2fa_login(test_user, backup_code)
    assert result is True

    # Verify code is marked as used
    code_obj = await TwoFactorBackupCode.get(code=backup_code)
    assert code_obj.is_used is True

    # Verify can't use same code again
    result = await TwoFactorService.verify_2fa_login(test_user, backup_code)
    assert result is False
