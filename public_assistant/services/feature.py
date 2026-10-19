"""فعال‌سازی دستیار عمومی."""
from __future__ import annotations

from django.conf import settings


def is_public_assistant_enabled() -> bool:
    return bool(getattr(settings, 'PUBLIC_ASSISTANT_ENABLED', False))


def widget_allowed_for_request(request) -> bool:
    if not is_public_assistant_enabled():
        return False
    path = (request.path or '').lower()
    blocked_prefixes = (
        '/workspace/',
        '/admin/',
        '/api/',
        '/payment/',
        '/accounts/login',
        '/accounts/register',
        '/accounts/password',
        '/accounts/reset',
    )
    if any(path.startswith(p) for p in blocked_prefixes):
        return False
    return True
