"""محدودسازی درخواست دستیار عمومی."""
from __future__ import annotations

import hashlib

from django.conf import settings
from django.core.cache import cache


class RateLimitExceeded(Exception):
    pass


def _client_ip(request) -> str:
    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    if forwarded:
        return forwarded
    return request.META.get('REMOTE_ADDR') or ''


def ip_hash(request) -> str:
    raw = _client_ip(request)
    salt = getattr(settings, 'SECRET_KEY', '')[:16]
    return hashlib.sha256(f'{salt}:{raw}'.encode()).hexdigest()


def _limits() -> tuple[int, int]:
    per_ip = int(getattr(settings, 'PUBLIC_ASSISTANT_RATE_LIMIT_PER_HOUR', 40))
    per_session = int(getattr(settings, 'PUBLIC_ASSISTANT_SESSION_RATE_LIMIT_PER_HOUR', 25))
    return per_ip, per_session


def check_rate_limit(request, session_id: str) -> None:
    per_ip, per_session = _limits()
    window = 3600
    ip_key = f'pa:rl:ip:{ip_hash(request)}'
    sess_key = f'pa:rl:sess:{session_id}'

    ip_count = cache.get(ip_key) or 0
    sess_count = cache.get(sess_key) or 0
    if ip_count >= per_ip or sess_count >= per_session:
        raise RateLimitExceeded()

    if ip_count == 0:
        cache.set(ip_key, 1, window)
    else:
        cache.incr(ip_key)

    if sess_count == 0:
        cache.set(sess_key, 1, window)
    else:
        cache.incr(sess_key)


def check_duplicate_request(session_id: str, message_norm: str) -> None:
    key = f'pa:dup:{session_id}:{hashlib.sha256(message_norm.encode()).hexdigest()[:16]}'
    if cache.get(key):
        raise RateLimitExceeded('duplicate')
    cache.set(key, 1, 15)
