"""استخراج FAQ از HTML مقالات برای Schema.org FAQPage."""
from __future__ import annotations

import re
from html import unescape

from django.utils.html import strip_tags

_FAQ_HEADING = re.compile(
    r'<h2[^>]*>\s*(?:سوالات\s*متداول|FAQ)[^<]*</h2>',
    re.IGNORECASE | re.UNICODE,
)
_H3_BLOCK = re.compile(r'<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>', re.DOTALL | re.IGNORECASE)


def extract_faq_pairs(html: str) -> list[tuple[str, str]]:
    """سؤال/جواب‌های بعد از سرتیتر «سوالات متداول»."""
    if not html:
        return []
    match = _FAQ_HEADING.search(html)
    if not match:
        return []
    tail = html[match.end():]
    pairs: list[tuple[str, str]] = []
    for q_raw, a_raw in _H3_BLOCK.findall(tail):
        q = _clean_text(q_raw)
        a = _clean_text(a_raw)
        if q and a:
            pairs.append((q, a))
    return pairs


def _clean_text(fragment: str) -> str:
    text = unescape(strip_tags(fragment or ''))
    return re.sub(r'\s+', ' ', text).strip()
