"""جنسیت مخاطب CRM — مقادیر canonical و نرمال‌سازی import/API."""
from __future__ import annotations

from typing import Any, Optional

CONTACT_GENDER_MALE = 'male'
CONTACT_GENDER_FEMALE = 'female'
CONTACT_GENDER_VALUES = frozenset({CONTACT_GENDER_MALE, CONTACT_GENDER_FEMALE})

CONTACT_GENDER_FORM_CHOICES = [
    ('', 'مشخص نشده'),
    (CONTACT_GENDER_FEMALE, 'خانم'),
    (CONTACT_GENDER_MALE, 'آقا'),
]

CONTACT_GENDER_EXPORT_LABELS = {
    CONTACT_GENDER_MALE: 'آقا',
    CONTACT_GENDER_FEMALE: 'خانم',
}

_IMPORT_ALIASES = {
    'male': CONTACT_GENDER_MALE,
    'm': CONTACT_GENDER_MALE,
    'man': CONTACT_GENDER_MALE,
    'مرد': CONTACT_GENDER_MALE,
    'آقا': CONTACT_GENDER_MALE,
    'اقا': CONTACT_GENDER_MALE,
    'female': CONTACT_GENDER_FEMALE,
    'f': CONTACT_GENDER_FEMALE,
    'woman': CONTACT_GENDER_FEMALE,
    'زن': CONTACT_GENDER_FEMALE,
    'خانم': CONTACT_GENDER_FEMALE,
}

_EMPTY_TOKENS = frozenset({
    '', 'nan', 'none', 'null', '-', '—', 'نامشخص', 'مشخص نشده', 'n/a',
})


def normalize_contact_gender_import(raw: Any) -> Optional[str]:
    """مقدار import — نامعتبر → None (import ادامه می‌یابد)."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.casefold() in _EMPTY_TOKENS:
        return None
    key = text.casefold()
    if key in CONTACT_GENDER_VALUES:
        return key
    if text in _IMPORT_ALIASES:
        return _IMPORT_ALIASES[text]
    if key in _IMPORT_ALIASES:
        return _IMPORT_ALIASES[key]
    return None


def parse_contact_gender_api(raw: Any) -> Optional[str]:
    """اعتبارسنجی API — نامعتبر ValueError."""
    if raw is None or raw == '':
        return None
    if not isinstance(raw, str):
        raw = str(raw)
    text = raw.strip()
    if not text:
        return None
    key = text.casefold()
    if key in CONTACT_GENDER_VALUES:
        return key
    normalized = normalize_contact_gender_import(text)
    if normalized:
        return normalized
    raise ValueError('مقدار جنسیت نامعتبر است. فقط male یا female مجاز است.')


def parse_contact_gender_nl(raw: Any) -> Optional[str]:
    """NL/AI — فقط male/female؛ نامعتبر → None (ambiguous در validator)."""
    if raw is None or raw == '':
        return None
    key = str(raw).strip().casefold()
    if key in CONTACT_GENDER_VALUES:
        return key
    normalized = normalize_contact_gender_import(raw)
    return normalized


def contact_gender_export_label(gender: Optional[str]) -> str:
    if not gender:
        return ''
    return CONTACT_GENDER_EXPORT_LABELS.get(gender, '')
