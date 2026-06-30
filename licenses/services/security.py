"""امنیت API لایسنس — rate limit، نرمال‌سازی ورودی، IP."""
from __future__ import annotations

import re
from typing import Optional

from django.conf import settings
from django.core.cache import cache

LICENSE_KEY_RE = re.compile(r'^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')
HW_FINGERPRINT_RE = re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int = 300):
        self.retry_after = retry_after
        super().__init__('تعداد درخواست‌های شما بیش از حد مجاز است.')


def get_client_ip(request_meta: dict) -> Optional[str]:
    forwarded = request_meta.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request_meta.get('REMOTE_ADDR')


def normalize_license_key(raw: str) -> str:
    return (raw or '').strip().upper()


def normalize_hardware_fingerprint(raw: str) -> str:
    return (raw or '').strip().lower()


def validate_license_key_format(license_key: str) -> bool:
    return bool(LICENSE_KEY_RE.match(license_key))


def validate_hardware_fingerprint_format(fingerprint: str) -> bool:
    return bool(HW_FINGERPRINT_RE.match(fingerprint))


def check_rate_limit(action: str, client_ip: Optional[str]) -> None:
    if not client_ip:
        return
    limits = {
        'activate': getattr(settings, 'LICENSE_RATE_LIMIT_ACTIVATE', 5),
        'validate': getattr(settings, 'LICENSE_RATE_LIMIT_VALIDATE', 60),
        'deactivate': getattr(settings, 'LICENSE_RATE_LIMIT_DEACTIVATE', 10),
        'import': getattr(settings, 'LICENSE_RATE_LIMIT_IMPORT', 20),
    }
    window = getattr(settings, 'LICENSE_RATE_LIMIT_WINDOW', 300)
    limit = limits.get(action, 30)
    cache_key = f'license_rl:{action}:{client_ip}'
    attempts = cache.get(cache_key, 0)
    if attempts >= limit:
        raise RateLimitExceeded(retry_after=window)
    cache.set(cache_key, attempts + 1, window)


def is_weak_license_secret() -> bool:
    secret = getattr(settings, 'LICENSE_SECRET_KEY', '') or ''
    weak_defaults = {
        'change-this-secret-key-in-production',
        '',
    }
    return secret in weak_defaults or len(secret) < 32
