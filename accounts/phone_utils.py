"""ابزارهای نرمال‌سازی و اعتبارسنجی شماره موبایل ایران."""
from __future__ import annotations

import re

from django.contrib.auth import get_user_model

PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def normalize_phone(raw: str) -> str:
    if not raw:
        return ''
    s = str(raw).strip().translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)
    s = re.sub(r'[\s\-()]+', '', s)
    if s.startswith('+98'):
        s = '0' + s[3:]
    elif s.startswith('0098'):
        s = '0' + s[4:]
    elif s.startswith('98') and len(s) == 12:
        s = '0' + s[2:]
    elif s.startswith('9') and len(s) == 10:
        s = '0' + s
    return s


def is_valid_iran_mobile(phone: str) -> bool:
    return bool(re.fullmatch(r'09\d{9}', phone or ''))


def phone_username(phone: str) -> str:
    digits = normalize_phone(phone).lstrip('0')
    return f'u{digits}'


def find_user_by_phone(phone: str):
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    User = get_user_model()
    return User.objects.filter(phone=normalized).first()
