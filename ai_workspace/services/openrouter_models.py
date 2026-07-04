"""لیست مدل‌های رایگان OpenRouter — refresh هر ۲۴ ساعت."""
from __future__ import annotations

from typing import List

import requests
from django.conf import settings
from django.core.cache import cache

_CACHE_KEY = 'ai_openrouter_free_models'
_CACHE_TTL = 86400  # 24h

_FALLBACK_MODELS = (
    'openrouter/free',
    'openai/gpt-oss-20b:free',
    'google/gemma-4-26b-a4b-it:free',
    'meta-llama/llama-3.2-3b-instruct:free',
)


def _parse_env_models() -> List[str]:
    raw = getattr(settings, 'OPENROUTER_FREE_MODELS', '') or ''
    models = [m.strip() for m in raw.split(',') if m.strip()]
    return [m for m in models if m.endswith(':free') or m == 'openrouter/free']


def refresh_free_models() -> List[str]:
    """از API مدل‌های :free را بگیرد؛ در صورت خطا env/fallback."""
    api_key = getattr(settings, 'OPENROUTER_API_KEY', '') or ''
    base = (getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1') or '').rstrip('/')
    if not api_key:
        return _parse_env_models() or list(_FALLBACK_MODELS)

    try:
        resp = requests.get(
            f'{base}/models',
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=8,
        )
        if not resp.ok:
            raise ValueError(f'HTTP {resp.status_code}')
        data = resp.json()
        free_ids = []
        for item in data.get('data') or []:
            mid = item.get('id') or ''
            if mid.endswith(':free') or mid == 'openrouter/free':
                free_ids.append(mid)
        if free_ids:
            cache.set(_CACHE_KEY, free_ids, _CACHE_TTL)
            return free_ids
    except Exception:
        pass

    env_models = _parse_env_models()
    if env_models:
        return env_models
    return list(_FALLBACK_MODELS)


def get_free_models() -> List[str]:
    cached = cache.get(_CACHE_KEY)
    if cached:
        return list(cached)
    return refresh_free_models()
