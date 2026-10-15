"""لینک‌های ثابت اتوماسیون رشد (تمدید، خرید، checkout)."""
from __future__ import annotations

from django.conf import settings
from django.urls import NoReverseMatch, reverse


def site_base_url() -> str:
    return (getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir').rstrip('/')


def abs_url(path_or_route: str, **reverse_kwargs) -> str:
    """مسیر مطلق یا نام URL Django → URL کامل."""
    if path_or_route.startswith('http://') or path_or_route.startswith('https://'):
        return path_or_route
    try:
        if ':' not in path_or_route and not path_or_route.startswith('/'):
            path = reverse(path_or_route, kwargs=reverse_kwargs or None)
        else:
            path = path_or_route
    except NoReverseMatch:
        path = path_or_route if path_or_route.startswith('/') else f'/{path_or_route}'
    if not path.startswith('/'):
        path = '/' + path
    return f'{site_base_url()}{path}'


def bot_buy_landing_url() -> str:
    """صفحه خرید/تمدید ربات — مسیر واقعی محصول در فروشگاه."""
    from shop.bot_catalog import get_bot_product_buy_url

    return abs_url(get_bot_product_buy_url())


def renewal_or_buy_landing_url() -> str:
    """
    لینک تمدید/خرید در SMSهای Growth.
    اگر LICENSE_RENEWAL_LANDING_URL در env تنظیم شده باشد همان؛
    در غیر این صورت صفحه buy محصول ربات.
    """
    explicit = (getattr(settings, 'LICENSE_RENEWAL_LANDING_URL', None) or '').strip()
    if explicit:
        return explicit
    return bot_buy_landing_url()
