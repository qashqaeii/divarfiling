"""ابزارهای نرمال‌سازی و اعتبارسنجی شماره موبایل ایران."""
from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

from django.contrib.auth import get_user_model

PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_ZERO_WIDTH = re.compile(r'[\u200c\u200d\ufeff\u00ad]')

_DIGIT_WORDS = {
    'صفر': '0',
    'یک': '1',
    'يک': '1',
    'یك': '1',
    'دو': '2',
    'سه': '3',
    'چهار': '4',
    'پنج': '5',
    'شش': '6',
    'هفت': '7',
    'هشت': '8',
    'نه': '9',
}

_SPOKEN_OPERATOR_PHRASES: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r'نه\s*صد\s*و\s*دوازده'), '912'),
    (re.compile(r'نه\s*صد\s*و\s*سیزده'), '913'),
    (re.compile(r'نه\s*صد\s*و\s*چهارده'), '914'),
    (re.compile(r'نه\s*صد\s*و\s*پانزده'), '915'),
    (re.compile(r'نه\s*صد\s*و\s*شانزده'), '916'),
    (re.compile(r'نه\s*صد\s*و\s*هفده'), '917'),
    (re.compile(r'نه\s*صد\s*و\s*هجده'), '918'),
    (re.compile(r'نه\s*صد\s*و\s*نوزده'), '919'),
)

_DIGIT_CANDIDATE_RE = re.compile(
    r'(?:\+?98|0098|0)?9[\d\s\-()۰-۹٠-٩]{8,12}',
    re.UNICODE,
)


def normalize_phone(raw: str) -> str:
    """نرمال‌سازی مستقیم یک مقدار شماره (نه استخراج از جمله)."""
    if not raw:
        return ''
    s = str(raw).strip().translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)
    s = _ZERO_WIDTH.sub('', s)
    s = re.sub(r'[\s\-().]+', '', s)
    if s.startswith('+'):
        s = s[1:]
    if s.startswith('0098'):
        s = '0' + s[4:]
    elif s.startswith('98') and len(s) >= 12:
        s = '0' + s[2:12]
    elif s.startswith('9') and len(s) == 10:
        s = '0' + s
    return s


def is_valid_iran_mobile(phone: str) -> bool:
    return bool(re.fullmatch(r'09\d{9}', phone or ''))


def is_valid_iran_landline(phone: str) -> bool:
    """تلفن ثابت ایران پس از normalize_phone."""
    p = normalize_phone(phone or '')
    if not p:
        return False
    return bool(re.fullmatch(r'0[1-8]\d{8,9}', p))


def is_valid_crm_phone(phone: str) -> bool:
    """موبایل یا ثابت معتبر برای CRM."""
    if not phone:
        return False
    p = normalize_phone(phone)
    return is_valid_iran_mobile(p) or is_valid_iran_landline(p)


def _apply_spoken_operator_phrases(text: str) -> str:
    out = text
    for pattern, repl in _SPOKEN_OPERATOR_PHRASES:
        out = pattern.sub(repl, out)
    return out


def _spoken_tokens_to_digit_stream(text: str) -> str:
    t = _apply_spoken_operator_phrases(text)
    t = t.translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)
    t = _ZERO_WIDTH.sub(' ', t)
    t = t.replace('ي', 'ی').replace('ك', 'ک')
    tokens = re.split(r'[\s,،؛\.]+', t)
    parts: List[str] = []
    for tok in tokens:
        token = (tok or '').strip()
        if not token or token == 'و':
            continue
        if token in _DIGIT_WORDS:
            parts.append(_DIGIT_WORDS[token])
            continue
        if re.fullmatch(r'\d+', token):
            parts.append(token)
            continue
        digits_only = re.sub(r'\D', '', token)
        if digits_only:
            parts.append(digits_only)
    return ''.join(parts)


def _unique_ordered(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _mobiles_from_digit_stream(digits: str) -> List[str]:
    found: List[str] = []
    if not digits:
        return found
    for match in re.finditer(r'09\d{9}', digits):
        candidate = match.group(0)
        if is_valid_iran_mobile(candidate):
            found.append(candidate)
    if found:
        return _unique_ordered(found)
    for match in re.finditer(r'9\d{9}', digits):
        candidate = '0' + match.group(0)
        if is_valid_iran_mobile(candidate):
            found.append(candidate)
    return _unique_ordered(found)


def extract_iran_mobiles_from_text(text: str) -> List[str]:
    """استخراج همه موبایل‌های معتبر ایران از متن (ترتیب ظاهر شدن)."""
    if not text or not str(text).strip():
        return []

    raw = str(text)
    found: List[str] = []

    direct = normalize_phone(raw)
    if is_valid_iran_mobile(direct):
        found.append(direct)

    cleaned = raw.translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)
    cleaned = _ZERO_WIDTH.sub('', cleaned)
    for match in _DIGIT_CANDIDATE_RE.finditer(cleaned):
        candidate = normalize_phone(match.group(0))
        if is_valid_iran_mobile(candidate):
            found.append(candidate)

    spoken_stream = _spoken_tokens_to_digit_stream(raw)
    found.extend(_mobiles_from_digit_stream(spoken_stream))

    return _unique_ordered(found)


def normalize_iran_mobile_from_text(text: str) -> Optional[str]:
    """اگر دقیقاً یک موبایل معتبر در متن باشد برمی‌گرداند؛ وگرنه None."""
    mobiles = extract_iran_mobiles_from_text(text)
    if len(mobiles) == 1:
        return mobiles[0]
    return None


def normalize_phone_field(
    raw: Any,
    *,
    user_text: str = '',
    allow_text_fallback: bool = True,
) -> Tuple[str, bool, bool]:
    """
    یک فیلد phone را normalize می‌کند.

    Returns:
        phone, was_invalid_attempt, ambiguous
    """
    raw_s = str(raw).strip() if raw not in (None, '') else ''
    if raw_s:
        direct = normalize_phone(raw_s)
        if is_valid_iran_mobile(direct):
            return direct, False, False
        extracted = extract_iran_mobiles_from_text(raw_s)
        if len(extracted) == 1:
            return extracted[0], False, False
        if len(extracted) >= 2:
            return '', False, True
        return '', True, False

    if allow_text_fallback and user_text:
        fallback = extract_iran_mobiles_from_text(user_text)
        if len(fallback) == 1:
            return fallback[0], False, False
        if len(fallback) >= 2:
            return '', False, True

    return '', False, False


def resolve_contact_phones(
    phone_raw: Any,
    phone_alt_raw: Any,
    *,
    user_text: str = '',
) -> Tuple[str, str, bool, bool]:
    """
    phone / phone_alt را از LLM و در صورت نیاز raw user_text resolve می‌کند.

    Returns:
        phone, phone_alt, phone_was_invalid, phone_ambiguous
    """
    phone_raw_s = str(phone_raw).strip() if phone_raw not in (None, '') else ''
    phone_alt_raw_s = str(phone_alt_raw).strip() if phone_alt_raw not in (None, '') else ''

    phone, phone_was_invalid, phone_ambiguous = normalize_phone_field(
        phone_raw_s or None,
        user_text='',
        allow_text_fallback=False,
    )

    phone_alt = ''
    if phone_alt_raw_s and not phone_ambiguous:
        phone_alt, _inv_alt, amb_alt = normalize_phone_field(
            phone_alt_raw_s,
            allow_text_fallback=False,
        )
        if amb_alt:
            phone_ambiguous = True
        elif phone_alt and phone_alt == phone:
            phone_ambiguous = True

    if phone_ambiguous:
        return '', '', phone_was_invalid or bool(phone_raw_s or phone_alt_raw_s), True

    if not phone and not phone_was_invalid:
        text_mobiles = extract_iran_mobiles_from_text(user_text)
        if not phone_raw_s and not phone_alt_raw_s:
            if len(text_mobiles) == 1:
                phone = text_mobiles[0]
            elif len(text_mobiles) == 2:
                phone, phone_alt = text_mobiles[0], text_mobiles[1]
            elif len(text_mobiles) >= 3:
                phone_ambiguous = True
        elif not phone_raw_s and len(text_mobiles) == 1:
            phone = text_mobiles[0]

    if phone_ambiguous:
        return '', '', phone_was_invalid, True

    if not phone and phone_raw_s:
        phone_was_invalid = True

    return phone, phone_alt, phone_was_invalid, phone_ambiguous


def phone_username(phone: str) -> str:
    digits = normalize_phone(phone).lstrip('0')
    return f'u{digits}'


def find_user_by_phone(phone: str):
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    User = get_user_model()
    return User.objects.filter(phone=normalized).first()
