"""اعتبارسنجی ورودی/خروجی دستیار عمومی."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from django.conf import settings

_INJECTION_PATTERNS = (
    re.compile(r'ignore\s+(all\s+)?previous\s+instructions', re.I),
    re.compile(r'system\s+prompt', re.I),
    re.compile(r'api[_\s-]?key', re.I),
    re.compile(r'توکن\s+دسترسی', re.I),
)

_ALLOWED_PRODUCTION_HOSTS = frozenset({'divarfiling.ir', 'www.divarfiling.ir'})
_DEBUG_HOSTS = frozenset({'localhost', '127.0.0.1'})


def _allowed_hosts() -> frozenset[str]:
    hosts = set(_ALLOWED_PRODUCTION_HOSTS)
    extra = getattr(settings, 'PUBLIC_ASSISTANT_ALLOWED_LINK_HOSTS', None) or []
    hosts.update(str(h).lower().strip() for h in extra if str(h).strip())
    if getattr(settings, 'DEBUG', False):
        hosts |= _DEBUG_HOSTS
    return frozenset(hosts)


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
    if any(c in url for c in ('\n', '\r', '\0', '<', '>', '"', "'")):
        return False
    if url.startswith('/'):
        if url.startswith('//'):
            return False
        if '..' in url.split('?')[0]:
            return False
        return True

    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False
    if parsed.username or parsed.password:
        return False
    host = (parsed.hostname or '').lower()
    if not host or host not in _allowed_hosts():
        return False
    if parsed.port and parsed.port not in (80, 443):
        return False
    return True


def filter_sources(links: list) -> list[dict]:
    from public_assistant.services.public_paths import canonical_public_path

    out = []
    for item in links or []:
        if isinstance(item, str):
            item = {'label': item, 'url': item}
        if not isinstance(item, dict):
            continue
        url = canonical_public_path((item.get('url') or '').strip())
        if not is_allowed_public_link(url):
            continue
        label = (item.get('label') or url).strip()[:200]
        out.append({'label': label or url, 'url': url})
    return out
