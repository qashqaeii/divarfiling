"""پل احراز هویت اپ → session میزکار برای WebView."""
from __future__ import annotations

import secrets
from typing import Optional, Tuple
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model

User = get_user_model()

CACHE_PREFIX = 'mobile_workspace_bridge:'
TTL_SECONDS = 300
ALLOWED_PREFIX = '/workspace/'


def _normalize_path(path: str) -> str:
    raw = (path or '').strip()
    if not raw:
        raise ValueError('مسیر الزامی است.')
    if raw.startswith('http://') or raw.startswith('https://'):
        parsed = urlparse(raw)
        raw = parsed.path or ''
        if parsed.query:
            raw = f'{raw}?{parsed.query}'
    if not raw.startswith('/'):
        raw = f'/{raw.lstrip("/")}'
    if not raw.startswith(ALLOWED_PREFIX):
        raise ValueError('مسیر مجاز نیست.')
    if '//' in raw.replace('://', ''):
        raise ValueError('مسیر نامعتبر است.')
    return raw


def create_bridge_token(user_id: int, redirect_path: str) -> Tuple[str, str]:
    path = _normalize_path(redirect_path)
    token = secrets.token_urlsafe(32)
    cache.set(
        f'{CACHE_PREFIX}{token}',
        {'user_id': int(user_id), 'path': path},
        TTL_SECONDS,
    )
    return token, path


def consume_bridge_token(token: str) -> Optional[dict]:
    key = f'{CACHE_PREFIX}{(token or "").strip()}'
    payload = cache.get(key)
    if not payload:
        return None
    cache.delete(key)
    return payload


def build_bridge_consume_url(token: str, *, request=None) -> str:
    rel = f'/workspace/app-bridge/{token}/'
    if request is not None:
        return request.build_absolute_uri(rel)
    site = getattr(settings, 'SITE_ORIGIN', '') or ''
    if site:
        return f'{site.rstrip("/")}{rel}'
    return rel
