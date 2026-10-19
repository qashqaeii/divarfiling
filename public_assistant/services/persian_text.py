"""نرمال‌سازی متن فارسی برای جست‌وجو."""
from __future__ import annotations

import re
import unicodedata

_ZWNJ = '\u200c'
_ARABIC_YEH = '\u064a'
_PERSIAN_YEH = '\u06cc'
_ARABIC_KAF = '\u0643'
_PERSIAN_KAF = '\u06a9'
_DIACRITICS = re.compile(r'[\u064b-\u065f\u0670]')
_WS = re.compile(r'\s+')


def normalize_persian(text: str) -> str:
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = text.replace(_ARABIC_YEH, _PERSIAN_YEH).replace(_ARABIC_KAF, _PERSIAN_KAF)
    text = text.replace('ك', _PERSIAN_KAF).replace('ي', _PERSIAN_YEH)
    text = _DIACRITICS.sub('', text)
    text = text.replace(_ZWNJ, ' ')
    text = _WS.sub(' ', text.strip().lower())
    return text


def tokenize_query(text: str) -> list[str]:
    norm = normalize_persian(text)
    parts = re.split(r'[^\w\u0600-\u06ff]+', norm)
    return [p for p in parts if len(p) >= 2]
