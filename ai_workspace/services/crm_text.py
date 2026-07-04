"""ابزارهای متن پیام CRM."""
from __future__ import annotations

import re

_EMOJI_RE = re.compile(
    '['
    '\U0001F300-\U0001FAFF'
    '\u2600-\u27BF'
    '\uFE0F'
    '\u200D'
    ']+',
    flags=re.UNICODE,
)


def sanitize_message_text(text: str) -> str:
    """حذف ایموجی — سازگاری با DB و prompt بدون emoji."""
    cleaned = _EMOJI_RE.sub('', text or '')
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()
