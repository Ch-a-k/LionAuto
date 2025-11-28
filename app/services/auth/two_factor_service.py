import pyotp
import qrcode
import io
import base64
import secrets
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from app.models.user import User
from app.models.two_factor_auth import TwoFactorBackupCode, TwoFactorAttempt, TwoFactorMethod
from app.services.communication.notification_service import NotificationService
from app.models.notification import NotificationType


class TwoFactorService:
    # ===================== utils =====================

    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret"""
        return pyotp.random_base32()

    @staticmethod
    def _normalize_code(code: str) -> str:
        """
        Приводим код к единому виду:
        - убираем пробелы по краям
        - убираем пробелы внутри
        - переводим в верхний регистр
        """
        return code.strip().replace(" ", "").upper()

    @staticmethod
    def generate_backup_codes(count: int = 10) -> list[str]:
        """
        Generate backup codes.

        Сейчас длина столбца в БД VARCHAR(45), но сами коды короче.
        Здесь мы оставляем удобочитаемый формат вида:

        XXXX-XXXX-XXXX-XXXX  (19 символов)

        Если захочешь, можно легко удлинить (например, 6 блоков по 4).
        """
        codes: list[str] = []
        for _ in range(count):
            raw = secrets.token_hex(8).upper()  # 16 hex chars
            formatted = f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}"
            codes.append(formatted)
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
        norm = TwoFactorService._normalize_code(code)
        totp = pyotp.TOTP(secret)
        # valid_window=1 → +/- одно 30-секундное окно
        return totp.verify(norm, valid_window=1)

    # ===================== enable / verify =====================

    @staticmethod
    async def enable_2fa(user: User) -> dict:
        """
        Enable 2FA for a user.

        Логика:
        - если уже включено → ошибка
        - очищаем старые backup-коды (чтобы не было мусора
          от предыдущих незавершённых попыток)
        - генерируем secret, QR и backup-коды
        - сохраняем secret в user.two_fa_secret
        - backup-коды сохраняем сразу, но они работают только при включённом 2FA
        """
        if user.two_fa_enabled:
            raise ValueError("2FA is already enabled")

        # На всякий случай очищаем все старые backup-коды
        await TwoFactorBackupCode.filter(user=user).delete()

        # Generate secret
        secret = TwoFactorService.generate_secret()

        # Generate QR code
        qr_code_url = TwoFactorService.generate_qr_code(user.email, secret)

        # Generate backup codes
        backup_codes = TwoFactorService.generate_backup_codes()

        # Store secret (pending until verification)
        user.two_fa_secret = secret
        await user.save()

        # Store backup codes
        # В БД сохраняем нормализованный вид (без пробелов, как есть)
        for code in backup_codes:
            await TwoFactorBackupCode.create(user=user, code=TwoFactorService._normalize_code(code))

        return {
            "secret": secret,
            "qr_code_url": qr_code_url,
            "backup_codes": backup_codes,  # человеку показываем красивый формат
        }

    @staticmethod
    async def verify_and_activate_2fa(
        user: User,
        code: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Verify code and activate 2FA"""
        if not user.two_fa_secret:
            raise ValueError("2FA setup not initiated")

        ok = TwoFactorService.verify_code(user.two_fa_secret, code)

        if ok:
            user.two_fa_enabled = True
            await user.save()

            await TwoFactorAttempt.create(
                user=user,
                method=TwoFactorMethod.totp,
                success=True,
                ip_address=ip_address
            )

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

    # ===================== disable =====================

    @staticmethod
    async def disable_2fa(
        user: User,
        code: str,
        password: str
    ) -> bool:
        """
        Disable 2FA.

        Требуем:
        - корректный пароль
        - либо актуальный TOTP, либо действующий backup-код.
        """
        if not user.two_fa_enabled:
            raise ValueError("2FA is not enabled")

        from app.core.security.pass_hash import verify_password

        # Verify password
        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid password")

        # 1) пробуем TOTP
        if user.two_fa_secret and TwoFactorService.verify_code(user.two_fa_secret, code):
            used_backup = False
        else:
            # 2) пробуем backup-код
            norm_code = TwoFactorService._normalize_code(code)
            backup_code = await TwoFactorBackupCode.get_or_none(
                user=user,
                code=norm_code,
                is_used=False
            )

            if not backup_code:
                # ни TOTP, ни backup не подошли
                await TwoFactorAttempt.create(
                    user=user,
                    method=TwoFactorMethod.backup_code if user.two_fa_enabled else TwoFactorMethod.totp,
                    success=False,
                    ip_address=None
                )
                return False

            # помечаем backup-код как использованный
            backup_code.is_used = True
            backup_code.used_at = datetime.now(timezone.utc)
            await backup_code.save()
            used_backup = True

        # Disable 2FA
        user.two_fa_enabled = False
        user.two_fa_secret = None
        await user.save()

        # Чистим ВСЕ backup-коды
        await TwoFactorBackupCode.filter(user=user).delete()

        # Логируем успешное отключение
        await TwoFactorAttempt.create(
            user=user,
            method=TwoFactorMethod.backup_code if used_backup else TwoFactorMethod.totp,
            success=True,
            ip_address=None
        )

        await NotificationService.create_notification(
            user=user,
            notification_type=NotificationType.two_fa_disabled,
            title="Two-Factor Authentication Disabled",
            message="Two-factor authentication has been disabled on your account."
        )

        return True

    # ===================== login verify =====================

    @staticmethod
    async def verify_2fa_login(
        user: User,
        code: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Verify 2FA code during login"""
        if not user.two_fa_enabled:
            # 2FA выключена — ничего не проверяем
            return True

        # Try TOTP code first
        if user.two_fa_secret and TwoFactorService.verify_code(user.two_fa_secret, code):
            await TwoFactorAttempt.create(
                user=user,
                method=TwoFactorMethod.totp,
                success=True,
                ip_address=ip_address
            )
            return True

        # Try backup code
        norm_code = TwoFactorService._normalize_code(code)
        backup_code = await TwoFactorBackupCode.get_or_none(
            user=user,
            code=norm_code,
            is_used=False
        )

        if backup_code:
            backup_code.is_used = True
            backup_code.used_at = datetime.now(timezone.utc)
            await backup_code.save()

            await TwoFactorAttempt.create(
                user=user,
                method=TwoFactorMethod.backup_code,
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

    # ===================== misc =====================

    @staticmethod
    async def get_backup_codes_count(user: User) -> int:
        """Get count of unused backup codes"""
        return await TwoFactorBackupCode.filter(user=user, is_used=False).count()
