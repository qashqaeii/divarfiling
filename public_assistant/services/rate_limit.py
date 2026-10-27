"""محدودسازی درخواست دستیار عمومی."""
from __future__ import annotations

import hashlib

from django.conf import settings
from django.core.cache import cache


class RateLimitExceeded(Exception):
    pass


def rate_limit_bypassed(request) -> bool:
    """مدیر سیستم (is_staff) هنگام استفاده از سایت لاگین‌شده — بدون سقف عمومی."""
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return bool(getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False))


def _trusted_proxy_ips() -> frozenset[str]:
    raw = getattr(settings, 'PUBLIC_ASSISTANT_TRUSTED_PROXY_IPS', None) or []
    return frozenset(str(x).strip() for x in raw if str(x).strip())


def _ip_from_x_forwarded_for(header: str) -> str:
    """
    آخرین IP در زنجیره X-Forwarded-For — با proxy_add_x_forwarded_for در Nginx
    مقدار تزریقی کلاینت در ابتدای هدر می‌آید و IP واقعی در انتها append می‌شود.
    """
    parts = [p.strip() for p in (header or '').split(',') if p.strip()]
    if not parts:
        return ''
    return parts[-1]


def client_ip(request) -> str:
    """IP بازدیدکننده — X-Forwarded-For فقط وقتی REMOTE_ADDR پراکسی معتبر است."""
    remote = (request.META.get('REMOTE_ADDR') or '').strip()
    if remote in _trusted_proxy_ips():
        forwarded = _ip_from_x_forwarded_for(request.META.get('HTTP_X_FORWARDED_FOR') or '')
        if forwarded:
            return forwarded
    return remote


def ip_hash(request) -> str:
    raw = client_ip(request)
    salt = getattr(settings, 'SECRET_KEY', '')[:16]
    return hashlib.sha256(f'{salt}:{raw}'.encode()).hexdigest()


def _consume(key: str, limit: int, window: int) -> bool:
    """یک واحد از سهمیه مصرف کن؛ False اگر سقف پر شده."""
    if limit <= 0:
        return True
    try:
        if cache.add(key, 1, window):
            return True
        count = cache.incr(key)
    except ValueError:
        cache.add(key, 1, window)
        return True
    return int(count) <= limit


def _limits() -> tuple[int, int]:
    per_ip = int(getattr(settings, 'PUBLIC_ASSISTANT_RATE_LIMIT_PER_HOUR', 40))
    per_session = int(getattr(settings, 'PUBLIC_ASSISTANT_SESSION_RATE_LIMIT_PER_HOUR', 25))
    return per_ip, per_session


def check_chat_rate_limit(request, session_id: str) -> None:
    if rate_limit_bypassed(request):
        return
    per_ip, per_session = _limits()
    window = 3600
    if not _consume(f'pa:rl:chat:ip:{ip_hash(request)}', per_ip, window):
        raise RateLimitExceeded('ip')
    if not _consume(f'pa:rl:chat:sess:{session_id}', per_session, window):
        raise RateLimitExceeded('session')


def check_session_create_rate(request) -> None:
    if rate_limit_bypassed(request):
        return
    limit = int(getattr(settings, 'PUBLIC_ASSISTANT_SESSION_CREATE_LIMIT_PER_HOUR', 12))
    window = 3600
    if not _consume(f'pa:rl:session:new:{ip_hash(request)}', limit, window):
        raise RateLimitExceeded('session_create')


def check_feedback_rate_limit(request, session_id: str) -> None:
    if rate_limit_bypassed(request):
        return
    limit = int(getattr(settings, 'PUBLIC_ASSISTANT_FEEDBACK_LIMIT_PER_HOUR', 30))
    if not _consume(f'pa:rl:feedback:ip:{ip_hash(request)}', limit, 3600):
        raise RateLimitExceeded('feedback')
    if not _consume(f'pa:rl:feedback:sess:{session_id}', 15, 3600):
        raise RateLimitExceeded('feedback_session')


def check_reset_rate_limit(request) -> None:
    if rate_limit_bypassed(request):
        return
    limit = int(getattr(settings, 'PUBLIC_ASSISTANT_RESET_LIMIT_PER_HOUR', 10))
    if not _consume(f'pa:rl:reset:ip:{ip_hash(request)}', limit, 3600):
        raise RateLimitExceeded('reset')


def check_duplicate_request(session_id: str, message_norm: str) -> None:
    key = f'pa:dup:{session_id}:{hashlib.sha256(message_norm.encode()).hexdigest()[:16]}'
    if cache.get(key):
        raise RateLimitExceeded('duplicate')
    cache.set(key, 1, 15)
