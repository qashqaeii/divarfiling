"""توکن‌ها، کوکی attribution و هش IP برای Lead Acquisition."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional

from django.conf import settings


COOKIE_NAME = 'df_lead_msg'
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def generate_click_token() -> str:
    return secrets.token_urlsafe(12)


def generate_idempotency_key(*, enrollment_id: int, step_number: int, variant_key: str) -> str:
    return f'leadmsg:{enrollment_id}:step{step_number}:v{variant_key}'


def hash_ip(raw_ip: Optional[str]) -> str:
    """IP خام ذخیره نمی‌شود — فقط HMAC-SHA256 کوتاه."""
    if not raw_ip:
        return ''
    secret = (getattr(settings, 'SECRET_KEY', '') or 'lead').encode('utf-8')
    digest = hmac.new(secret, raw_ip.encode('utf-8'), hashlib.sha256).hexdigest()
    return digest[:32]


def truncate_user_agent(ua: Optional[str], limit: int = 300) -> str:
    return (ua or '')[:limit]


def cookie_secure_kwargs() -> dict:
    return {
        'max_age': COOKIE_MAX_AGE,
        'httponly': True,
        'secure': not getattr(settings, 'DEBUG', False),
        'samesite': 'Lax',
        'path': '/',
    }
