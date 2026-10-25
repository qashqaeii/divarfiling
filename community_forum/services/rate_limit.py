"""محدودیت ارسال — اتمیک با Redis در صورت موجودبودن."""
import logging
import time

from django.conf import settings
from django.core.cache import caches
from django.core.exceptions import ValidationError

from community_forum.constants import (
    MAX_MESSAGES_PER_HOUR,
    MAX_MESSAGES_PER_MINUTE,
    MIN_SEND_INTERVAL_SECONDS,
)

logger = logging.getLogger(__name__)

CACHE_ALIAS = 'forum_rate_limit'

_LUA_ENFORCE = """
local last_key = KEYS[1]
local min_key = KEYS[2]
local hour_key = KEYS[3]
local now = tonumber(ARGV[1])
local min_interval = tonumber(ARGV[2])
local per_min = tonumber(ARGV[3])
local per_hour = tonumber(ARGV[4])

local last = redis.call('GET', last_key)
if last and (now - tonumber(last)) < min_interval then
  return {0, 'interval'}
end

local mc = tonumber(redis.call('GET', min_key) or '0')
if mc >= per_min then
  return {0, 'minute'}
end
local hc = tonumber(redis.call('GET', hour_key) or '0')
if hc >= per_hour then
  return {0, 'hour'}
end

redis.call('SET', last_key, now, 'EX', min_interval + 2)
mc = redis.call('INCR', min_key)
if mc == 1 then redis.call('EXPIRE', min_key, 60) end
hc = redis.call('INCR', hour_key)
if hc == 1 then redis.call('EXPIRE', hour_key, 3600) end
return {1, 'ok'}
"""


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


def _redis_client():
    url = getattr(settings, 'FORUM_REDIS_URL', '') or ''
    if not url:
        return None
    try:
        import redis

        return redis.from_url(url, decode_responses=True)
    except Exception:
        logger.exception('forum rate limit redis unavailable')
        return None


def _raise_rate(code: str):
    messages = {
        'interval': 'لطفاً چند ثانیه صبر کنید و دوباره ارسال کنید.',
        'minute': 'حد مجاز ارسال در این دقیقه پر شده است.',
        'hour': 'حد مجاز ارسال در این ساعت پر شده است.',
    }
    raise ValidationError(messages.get(code, 'محدودیت ارسال'), code=f'rate_{code}')


def _enforce_redis(member_id: int, user, limits: dict) -> None:
    client = _redis_client()
    if client is None:
        if getattr(settings, 'COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS', False):
            raise ValidationError('سرویس محدودیت ارسال موقتاً در دسترس نیست.', code='rate_unavailable')
        _enforce_cache_fallback(member_id, user, limits)
        return
    now = time.time()
    keys = [
        f'forum:rl:{member_id}:last',
        f'forum:rl:{member_id}:min',
        f'forum:rl:{member_id}:hour',
    ]
    try:
        result = client.eval(
            _LUA_ENFORCE,
            3,
            *keys,
            now,
            limits['min_interval'],
            limits['per_minute'],
            limits['per_hour'],
        )
    except Exception:
        logger.exception('forum rate limit redis eval failed')
        if getattr(settings, 'COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS', False):
            raise ValidationError('سرویس محدودیت ارسال موقتاً در دسترس نیست.', code='rate_unavailable')
        _enforce_cache_fallback(member_id, user, limits)
        return
    if not result or int(result[0]) != 1:
        _raise_rate(str(result[1]) if result else 'interval')


def _enforce_cache_fallback(member_id: int, user, limits: dict) -> None:
    """فقط dev/test — در production FORUM_REDIS_URL تنظیم شود."""
    cache = _cache()
    now = time.time()
    last_key = f'forum:rl:{member_id}:last'
    min_key = f'forum:rl:{member_id}:min'
    hour_key = f'forum:rl:{member_id}:hour'

    last = cache.get(last_key)
    if last is not None and (now - float(last)) < limits['min_interval']:
        _raise_rate('interval')

    minute_count = cache.get(min_key, 0)
    if minute_count >= limits['per_minute']:
        _raise_rate('minute')

    hour_count = cache.get(hour_key, 0)
    if hour_count >= limits['per_hour']:
        _raise_rate('hour')

    cache.set(last_key, now, timeout=limits['min_interval'] + 2)
    try:
        cache.incr(min_key)
    except ValueError:
        cache.set(min_key, 1, timeout=60)
    try:
        cache.incr(hour_key)
    except ValueError:
        cache.set(hour_key, 1, timeout=3600)


def enforce_send_rate_limit(member_id: int, user) -> None:
    limits = _limits_for_user(user)
    _enforce_redis(member_id, user, limits)
