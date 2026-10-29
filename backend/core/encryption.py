"""
core/encryption.py

Symmetric encryption for sensitive data at rest (BYOK API keys).
Enforces Rule 39: "API keys and credentials are encrypted at rest and scoped per user."
Uses AES-128-CBC via Fernet with key derived from Django SECRET_KEY.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet() -> Fernet:
    """Derive a deterministic 32-byte Fernet key from SECRET_KEY or CREDENTIALS_ENCRYPTION_KEY."""
    custom_key = getattr(settings, "CREDENTIALS_ENCRYPTION_KEY", None) or os.getenv("CREDENTIALS_ENCRYPTION_KEY")
    if custom_key:
        raw_key = custom_key.encode("utf-8")
    else:
        raw_key = settings.SECRET_KEY.encode("utf-8")

    derived_key = base64.urlsafe_b64encode(hashlib.sha256(raw_key).digest())
    return Fernet(derived_key)


def encrypt_secret(plain_text: str) -> str:
    """Encrypts plaintext string to URL-safe base64 ciphertext string."""
    if not plain_text:
        return ""
    f = _get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    """Decrypts ciphertext string back to plaintext."""
    if not cipher_text:
        return ""
    f = _get_fernet()
    return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")


def mask_api_key(key: str) -> str:
    """
    Returns masked representation of an API key (e.g. 'sk-...4a9f').
    Safe to display in UI and API responses. Never leaks full key.
    """
    if not key:
        return ""
    clean = key.strip()
    if len(clean) <= 8:
        return "••••"
    return f"{clean[:3]}...{clean[-4:]}"

