from enum import Enum


class TwoFactorMethod(str, Enum):
    totp = "totp"  # Time-based One-Time Password
    sms = "sms"
    email = "email"
