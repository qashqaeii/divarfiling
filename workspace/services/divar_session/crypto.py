"""رمزنگاری payload نشست دیوار در دیتابیس."""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class DivarSessionCryptoError(Exception):
    pass


def _fernet_key_bytes() -> bytes:
    raw = (getattr(settings, 'DIVAR_SESSION_ENCRYPTION_KEY', None) or '').strip()
    if raw:
        return raw.encode('utf-8')
    digest = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_payload(data: dict[str, Any]) -> str:
    token = Fernet(_fernet_key_bytes()).encrypt(
        json.dumps(data, ensure_ascii=False).encode('utf-8'),
    )
    return token.decode('ascii')


def decrypt_payload(token: str) -> dict[str, Any]:
    if not token:
        return {}
    try:
        raw = Fernet(_fernet_key_bytes()).decrypt(token.encode('ascii'))
    except InvalidToken as exc:
        raise DivarSessionCryptoError('نشست رمزگشایی نشد.') from exc
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DivarSessionCryptoError('فرمت نشست نامعتبر است.') from exc
    return data if isinstance(data, dict) else {}
