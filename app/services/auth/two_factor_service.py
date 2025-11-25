import pyotp
import qrcode
import io
import base64
import secrets
from typing import Optional
from uuid import UUID

from app.models.user import User
from app.models.two_factor_auth import TwoFactorBackupCode, TwoFactorAttempt, TwoFactorMethod
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType


class TwoFactorService:
    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret"""
        return pyotp.random_base32()

    @staticmethod
    def generate_backup_codes(count: int = 10) -> list[str]:
        """Generate backup codes"""
        codes = []
        for _ in range(count):
            code = secrets.token_hex(8).upper()
            codes.append(f"{code[:4]}-{code[4:8]}-{code[8:12]}-{code[12:16]}")
        return codes

    @staticmethod
    def generate_qr_code(user_email: str, secret: str, issuer: str = "LA Auction") -> str:
        """Generate QR code as base64 data URL"""
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user_email,
            issuer_name=issuer
        )

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_base64}"

    @staticmethod
    def verify_code(secret: str, code: str) -> bool:
        """Verify a TOTP code"""
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)

    @staticmethod
    async def enable_2fa(user: User) -> dict:
        """Enable 2FA for a user"""
        if user.two_fa_enabled:
            raise ValueError("2FA is already enabled")

        # Generate secret
        secret = TwoFactorService.generate_secret()

        # Generate QR code
        qr_code_url = TwoFactorService.generate_qr_code(user.email, secret)

        # Generate backup codes
        backup_codes = TwoFactorService.generate_backup_codes()

        # Store secret (temporarily, will be confirmed on first verification)
        user.two_fa_secret = secret
        await user.save()

        # Store backup codes
        for code in backup_codes:
            await TwoFactorBackupCode.create(user=user, code=code)

        return {
            "secret": secret,
            "qr_code_url": qr_code_url,
            "backup_codes": backup_codes
        }

    @staticmethod
    async def verify_and_activate_2fa(user: User, code: str, ip_address: Optional[str] = None) -> bool:
        """Verify code and activate 2FA"""
        if not user.two_fa_secret:
            raise ValueError("2FA setup not initiated")

        if TwoFactorService.verify_code(user.two_fa_secret, code):
            user.two_fa_enabled = True
            await user.save()

            # Log attempt
            await TwoFactorAttempt.create(
                user=user,
                method=TwoFactorMethod.totp,
                success=True,
                ip_address=ip_address
            )

            # Send notification
            await NotificationService.create_notification(
                user=user,
                notification_type=NotificationType.two_fa_enabled,
                title="Two-Factor Authentication Enabled",
                message="Two-factor authentication has been successfully enabled on your account."
            )

            return True

        # Log failed attempt
        await TwoFactorAttempt.create(
            user=user,
            method=TwoFactorMethod.totp,
            success=False,
            ip_address=ip_address
        )

        return False

    @staticmethod
    async def disable_2fa(user: User, code: str, password: str) -> bool:
        """Disable 2FA"""
        if not user.two_fa_enabled:
            raise ValueError("2FA is not enabled")

        # Verify password
        from app.core.security.pass_hash import verify_password
        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid password")

        # Verify 2FA code
        if not TwoFactorService.verify_code(user.two_fa_secret, code):
            return False

        # Disable 2FA
        user.two_fa_enabled = False
        user.two_fa_secret = None
        await user.save()

        # Delete backup codes
        await TwoFactorBackupCode.filter(user=user).delete()

        # Send notification
        await NotificationService.create_notification(
            user=user,
            notification_type=NotificationType.two_fa_disabled,
            title="Two-Factor Authentication Disabled",
            message="Two-factor authentication has been disabled on your account."
        )

        return True

    @staticmethod
    async def verify_2fa_login(user: User, code: str, ip_address: Optional[str] = None) -> bool:
        """Verify 2FA code during login"""
        if not user.two_fa_enabled:
            return True

        # Try TOTP code first
        if TwoFactorService.verify_code(user.two_fa_secret, code):
            await TwoFactorAttempt.create(
                user=user,
                method=TwoFactorMethod.totp,
                success=True,
                ip_address=ip_address
            )
            return True

        # Try backup codes
        backup_code = await TwoFactorBackupCode.get_or_none(
            user=user,
            code=code,
            is_used=False
        )

        if backup_code:
            backup_code.is_used = True
            from datetime import datetime
            backup_code.used_at = datetime.utcnow()
            await backup_code.save()

            await TwoFactorAttempt.create(
                user=user,
                method=TwoFactorMethod.totp,
                success=True,
                ip_address=ip_address
            )

            return True

        # Log failed attempt
        await TwoFactorAttempt.create(
            user=user,
            method=TwoFactorMethod.totp,
            success=False,
            ip_address=ip_address
        )

        return False

    @staticmethod
    async def get_backup_codes_count(user: User) -> int:
        """Get count of unused backup codes"""
        return await TwoFactorBackupCode.filter(user=user, is_used=False).count()
