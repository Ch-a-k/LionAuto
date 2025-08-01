import re
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings

ENCRYPTION_KEY = settings.ENCRYPTION_KEY  # bytes, длина 32

def validate_username(auction_type: str, username: str) -> bool:
    if auction_type == "copart":
        return bool(re.fullmatch(r"[a-zA-Z0-9]{5,20}", username))
    elif auction_type == "iaai":
        return bool(re.fullmatch(r"\d{8}", username))
    elif auction_type == "manheim":
        return bool(re.fullmatch(r"[a-zA-Z0-9]{6,15}", username))
    return False

def encrypt(data: bytes) -> bytes:
    aesgcm = AESGCM(ENCRYPTION_KEY)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, data, None)
    return nonce + ct

def decrypt(token: bytes) -> bytes:
    aesgcm = AESGCM(ENCRYPTION_KEY)
    nonce = token[:12]
    ct = token[12:]
    return aesgcm.decrypt(nonce, ct, None)
