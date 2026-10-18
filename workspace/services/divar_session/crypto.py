"""رمزنگاری payload نشست دیوار در دیتابیس."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any, Iterable

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


class DivarSessionCryptoError(Exception):
    pass


def _normalize_fernet_key(raw: str) -> bytes | None:
    value = (raw or '').strip()
    if not value:
        return None
    try:
        Fernet(value.encode('utf-8'))
    except (TypeError, ValueError):
        logger.warning('DIVAR_SESSION encryption key ignored: invalid Fernet key format')
        return None
    return value.encode('utf-8')


def _secret_key_derived_fernet() -> bytes:
    digest = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


def encryption_keys_for_decrypt() -> list[bytes]:
    """ترتیب امتحان برای رمزگشایی — سازگاری با نشست‌های قبلی."""
    keys: list[bytes] = []
    seen: set[bytes] = set()

    def _add(raw: str) -> None:
        key = _normalize_fernet_key(raw)
        if key and key not in seen:
            keys.append(key)
            seen.add(key)

    _add(getattr(settings, 'DIVAR_SESSION_ENCRYPTION_KEY', None) or '')
    _add(getattr(settings, 'DIVAR_SESSION_ENCRYPTION_KEY_LEGACY', None) or '')
    derived = _secret_key_derived_fernet()
    if derived not in seen:
        keys.append(derived)
    return keys


def encryption_key_for_encrypt() -> bytes:
    primary = _normalize_fernet_key(getattr(settings, 'DIVAR_SESSION_ENCRYPTION_KEY', None) or '')
    if primary:
        return primary
    return _secret_key_derived_fernet()


def encrypt_payload(data: dict[str, Any]) -> str:
    token = Fernet(encryption_key_for_encrypt()).encrypt(
        json.dumps(data, ensure_ascii=False).encode('utf-8'),
    )
    return token.decode('ascii')


def decrypt_payload(token: str) -> dict[str, Any]:
    if not token:
        return {}
    last_error: InvalidToken | None = None
    for key in encryption_keys_for_decrypt():
        try:
            raw = Fernet(key).decrypt(token.encode('ascii'))
            break
        except InvalidToken as exc:
            last_error = exc
            continue
    else:
        raise DivarSessionCryptoError('نشست رمزگشایی نشد.') from last_error
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DivarSessionCryptoError('فرمت نشست نامعتبر است.') from exc
    return data if isinstance(data, dict) else {}
