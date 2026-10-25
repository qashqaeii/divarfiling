"""محدودیت ارسال — cache جدا از default سایت."""
import time

from django.conf import settings
from django.core.cache import caches
from django.core.exceptions import ValidationError

from community_forum.constants import (
    MAX_MESSAGES_PER_HOUR,
    MAX_MESSAGES_PER_MINUTE,
    MIN_SEND_INTERVAL_SECONDS,
)

CACHE_ALIAS = 'forum_rate_limit'


def _cache():
    return caches[CACHE_ALIAS]


def _limits_for_user(user):
    base = {
        'min_interval': getattr(settings, 'COMMUNITY_FORUM_MIN_SEND_INTERVAL', MIN_SEND_INTERVAL_SECONDS),
        'per_minute': getattr(settings, 'COMMUNITY_FORUM_MAX_PER_MINUTE', MAX_MESSAGES_PER_MINUTE),
        'per_hour': getattr(settings, 'COMMUNITY_FORUM_MAX_PER_HOUR', MAX_MESSAGES_PER_HOUR),
    }
    joined = getattr(user, 'date_joined', None)
    if joined:
        from django.utils import timezone

        age_days = (timezone.now() - joined).days
        if age_days < 7:
            base['per_minute'] = min(base['per_minute'], 5)
            base['per_hour'] = min(base['per_hour'], 30)
            base['min_interval'] = max(base['min_interval'], 5)
    return base


def enforce_send_rate_limit(member_id: int, user) -> None:
    cache = _cache()
    limits = _limits_for_user(user)
    now = time.time()
    last_key = f'forum:rl:{member_id}:last'
    min_key = f'forum:rl:{member_id}:min'
    hour_key = f'forum:rl:{member_id}:hour'

    last = cache.get(last_key)
    if last is not None and (now - float(last)) < limits['min_interval']:
        raise ValidationError(
            'لطفاً چند ثانیه صبر کنید و دوباره ارسال کنید.',
            code='rate_interval',
        )

    minute_count = cache.get(min_key, 0)
    if minute_count >= limits['per_minute']:
        raise ValidationError('حد مجاز ارسال در این دقیقه پر شده است.', code='rate_minute')

    hour_count = cache.get(hour_key, 0)
    if hour_count >= limits['per_hour']:
        raise ValidationError('حد مجاز ارسال در این ساعت پر شده است.', code='rate_hour')

    cache.set(last_key, now, timeout=limits['min_interval'] + 2)
    if minute_count == 0:
        cache.set(min_key, 1, timeout=60)
    else:
        try:
            cache.incr(min_key)
        except ValueError:
            cache.set(min_key, 1, timeout=60)

    if hour_count == 0:
        cache.set(hour_key, 1, timeout=3600)
    else:
        try:
            cache.incr(hour_key)
        except ValueError:
            cache.set(hour_key, 1, timeout=3600)
