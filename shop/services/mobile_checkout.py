"""علامت سفارش‌هایی که از اپ موبایل شروع شده‌اند — بدون تغییر schema."""
from django.core.cache import cache

CACHE_PREFIX = 'mobile_checkout:'
TTL_SECONDS = 60 * 60 * 6


def mark_mobile_checkout(order_id) -> None:
    cache.set(f'{CACHE_PREFIX}{order_id}', 1, TTL_SECONDS)


def is_mobile_checkout(order_id) -> bool:
    return bool(cache.get(f'{CACHE_PREFIX}{order_id}'))
