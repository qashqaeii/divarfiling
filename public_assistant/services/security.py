"""اعتبارسنجی ورودی/خروجی دستیار عمومی."""
from __future__ import annotations

import re
from urllib.parse import urlparse

_INJECTION_PATTERNS = (
    re.compile(r'ignore\s+(all\s+)?previous\s+instructions', re.I),
    re.compile(r'system\s+prompt', re.I),
    re.compile(r'api[_\s-]?key', re.I),
    re.compile(r'توکن\s+دسترسی', re.I),
)

def _allowed_prefixes():
    from django.conf import settings

    base = ('/', 'https://divarfiling.ir', 'https://www.divarfiling.ir')
    if getattr(settings, 'DEBUG', False):
        return base + ('http://127.0.0.1', 'http://localhost')
    return base


def looks_like_prompt_injection(text: str) -> bool:
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return True
    return False


def sanitize_user_message(text: str, max_len: int) -> str:
    cleaned = (text or '').strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned


def is_allowed_public_link(url: str) -> bool:
    if not url:
        return False
    url = url.strip()
    if url.startswith('/'):
        return not url.startswith('//')
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False
    full = f'{parsed.scheme}://{parsed.netloc}'
    return any(url.startswith(p) or full == p.rstrip('/') for p in _allowed_prefixes())


def filter_sources(links: list) -> list[dict]:
    out = []
    for item in links or []:
        if isinstance(item, str):
            item = {'label': item, 'url': item}
        if not isinstance(item, dict):
            continue
        url = (item.get('url') or '').strip()
        if is_allowed_public_link(url):
            out.append({'label': item.get('label') or url, 'url': url})
    return out
