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

STOPWORDS = frozenset(
    {
        'از',
        'به',
        'در',
        'با',
        'برای',
        'که',
        'این',
        'آن',
        'را',
        'رو',
        'یه',
        'یک',
        'من',
        'شما',
        'می',
        'چطور',
        'چگونه',
        'چی',
        'چیه',
        'است',
        'هست',
        'کرد',
        'کنم',
        'کنید',
        'the',
        'and',
    }
)

# گسترش پرسش محاوره‌ای → واژه‌های دانشنامه
QUERY_SYNONYMS: dict[str, list[str]] = {
    'مشتری': ['مخاطب', 'خریدار', 'مراجع', 'crm'],
    'مخاطب': ['مشتری', 'خریدار', 'crm'],
    'خریدار': ['مشتری', 'مخاطب'],
    'لاگین': ['ورود', 'ثبت'],
    'ورود': ['لاگین', 'login'],
    'قیمت': ['پلن', 'لایسنس', 'اشتراک', 'خرید'],
    'اشتراک': ['لایسنس', 'پلن'],
    'لایسنس': ['اشتراک', 'کلید', 'فعال'],
    'استخراج': ['ربات', 'اسکرپ', 'کشیدن', 'آگهی'],
    'ربات': ['استخراج', 'extractor'],
    'فایلینگ': ['dataset', 'مجموعه', 'فایل'],
    'فایل': ['فایلینگ', 'dataset', 'آگهی'],
    'آژانس': ['تیم', 'agency'],
    'هوش': ['ai', 'هوشمند'],
    'فرمان': ['nl', 'دستور'],
    'هدیه': ['آزمایشی', 'هفت', 'trial'],
    'اندروید': ['android', 'موبایل', 'اپ'],
    'ویندوز': ['windows', 'دسکتاپ'],
}


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


def expand_query_tokens(tokens: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        if tok in seen:
            continue
        seen.add(tok)
        expanded.append(tok)
        for alt in QUERY_SYNONYMS.get(tok, []):
            alt_n = normalize_persian(alt)
            if alt_n and alt_n not in seen and len(alt_n) >= 2:
                seen.add(alt_n)
                expanded.append(alt_n)
    return expanded


def tokenize_query(text: str) -> list[str]:
    norm = normalize_persian(text)
    parts = re.split(r'[^\w\u0600-\u06ff]+', norm)
    tokens = [p for p in parts if len(p) >= 2 and p not in STOPWORDS]
    return expand_query_tokens(tokens)
