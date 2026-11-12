"""مسیرهای رسمی سایت برای پاسخ دستیار عمومی — نرمال‌سازی و فیلتر لینک."""
from __future__ import annotations

import re

from public_assistant.services.security import is_allowed_public_link

_MD_LINK_URL_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

_PATH_ALIASES: dict[str, str] = {
    '/contact-us/': '/contact/',
    '/contact-us': '/contact/',
    '/support/': '/workspace/support/',
    '/support': '/workspace/support/',
}

_COMMERCE_PREFIXES = (
    '/products/',
    '/payment/',
)


def _alias_lookup(path_part: str) -> str | None:
    candidates = (
        path_part,
        path_part.rstrip('/') + '/',
        path_part + '/',
    )
    for key in candidates:
        if key in _PATH_ALIASES:
            return _PATH_ALIASES[key]
    return None


def canonical_public_path(url: str) -> str:
    """یکسان‌سازی مسیر نسبی قبل از نمایش یا فیلتر."""
    raw = (url or '').strip()
    if not raw or not raw.startswith('/'):
        return raw
    if '?' in raw:
        path_part, query = raw.split('?', 1)
        query = '?' + query
    else:
        path_part, query = raw, ''
    alias = _alias_lookup(path_part)
    if alias:
        path_part = alias
    out = path_part + query
    if not is_allowed_public_link(out):
        return raw
    return out


def is_commerce_path(url: str) -> bool:
    base = (url or '').split('?')[0].rstrip('/') + '/'
    return any(base.startswith(p) for p in _COMMERCE_PREFIXES)


def scrub_commerce_links_from_answer(text: str) -> str:
    """حذف لینک خرید/پرداخت از پاسخ سؤالات غیراشتراکی."""
    if not text:
        return text

    def _link_repl(m: re.Match[str]) -> str:
        label, url = m.group(1), m.group(2).strip()
        if is_commerce_path(url):
            return label
        return m.group(0)

    return _MD_LINK_URL_RE.sub(_link_repl, text)
