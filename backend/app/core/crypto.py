"""Fernet 对称加密：用于 providers.api_key 落库。"""

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _dev_key() -> bytes:
    """开发环境：由 jwt_secret 派生 32 字节 key（生产必须显式配置 fernet_key）。"""
    digest = hashlib.sha256(get_settings().jwt_secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.fernet_key.encode() if settings.fernet_key else _dev_key()
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
