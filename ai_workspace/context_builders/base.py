"""ابزارهای Context Builder."""
from __future__ import annotations

import re


def truncate(text: str, max_len: int = 300) -> str:
    text = (text or '').strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + '…'


def mask_phone(text: str) -> str:
    if not text:
        return text
    return re.sub(r'09\d{9}', '[شماره]', text)
