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
    'قیمت': ['پلن', 'لایسنس', 'اشتراک', 'خرید', 'چنده'],
    'چنده': ['قیمت', 'پلن', 'هزینه'],
    'اشتراک': ['لایسنس', 'پلن', 'خرید'],
    'لایسنس': ['اشتراک', 'کلید', 'فعال', 'license'],
    'استخراج': ['ربات', 'اسکرپ', 'کشیدن', 'آگهی', 'extractor'],
    'ربات': ['استخراج', 'extractor'],
    'فایلینگ': ['dataset', 'مجموعه', 'فایل', 'میزکار'],
    'فایل': ['فایلینگ', 'dataset', 'آگهی'],
    'آژانس': ['تیم', 'agency', 'دفتر'],
    'هوش': ['ai', 'هوشمند', 'مصنوعی'],
    'مصنوعی': ['ai', 'هوش'],
    'فرمان': ['nl', 'دستور', 'هوشمند'],
    'هدیه': ['آزمایشی', 'هفت', 'trial', 'رایگان'],
    'اندروید': ['android', 'موبایل', 'اپ'],
    'ویندوز': ['windows', 'دسکتاپ'],
    'شماره': ['تماس', 'موبایل', 'تلفن'],
    'تماس': ['شماره', 'تلفن'],
    'تطبیق': ['match', 'مناسب', 'پیشنهاد', 'مچینگ'],
    'مچینگ': ['تطبیق', 'match', 'پیشنهاد'],
    'زونکن': ['پوشه', 'کمد', 'دسته'],
    'پوشه': ['زونکن', 'کمد'],
    'وصل': ['اتصال', 'همگام', 'ربات', 'connect'],
    'ربات': ['استخراج', 'extractor', 'وصل'],
    'شناور': ['overlay', 'پنجره', 'تماس'],
    'تالار': ['forum', 'گفتگو', 'انجمن'],
    'نقشه': ['map', 'موقعیت'],
    'گروهی': ['دسته', 'batch', 'لیست'],
    'تمدید': ['renew', 'انقضا'],
    'صندلی': ['seat', 'نفر', 'لایسنس'],
    'میزکار': ['workspace', 'فایلینگ'],
    'دیوار': ['divar', 'آگهی'],
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


def expand_query_tokens(tokens: list[str], *, link_customer: bool = False) -> list[str]:
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
                if link_customer and tok in ('مشتری', 'مخاطب') and alt_n in (
                    'crm',
                    'مخاطب',
                    'خریدار',
                    'مراجع',
                    'مشتری',
                ):
                    continue
                seen.add(alt_n)
                expanded.append(alt_n)
    return expanded


def tokenize_query(text: str) -> list[str]:
    norm = normalize_persian(text)
    parts = re.split(r'[^\w\u0600-\u06ff]+', norm)
    tokens = [p for p in parts if len(p) >= 2 and p not in STOPWORDS]
    link_customer = 'لینک' in norm and any(
        w in norm for w in ('مشتری', 'share', 'عمومی', 'بفرست', 'ارسال', 'بساز')
    )
    return expand_query_tokens(tokens, link_customer=link_customer)
