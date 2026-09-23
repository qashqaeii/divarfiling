"""ابزارهای Context Builder."""
from __future__ import annotations

import re

_PHONE_PATTERNS = (
    re.compile(r'09\d{9}'),
    re.compile(r'\+98\s*9\d{9}'),
    re.compile(r'0098\s*9\d{9}'),
    re.compile(r'(?<!\d)9\d{9}(?!\d)'),
)
_EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    flags=re.IGNORECASE,
)


def truncate(text: str, max_len: int = 300) -> str:
    text = (text or '').strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + '…'


def mask_phone(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern in _PHONE_PATTERNS:
        out = pattern.sub('[شماره]', out)
    return out


def redact_pii_text(text: str) -> str:
    """حذف/ماسک PII از متن آزاد قبل از ارسال به LLM."""
    if not text:
        return text
    out = mask_phone(text)
    out = _EMAIL_RE.sub('[ایمیل]', out)
    return out
