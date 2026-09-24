"""نام نمایشی کاربر در CRM و آژانس — username قبل از شماره موبایل."""
from __future__ import annotations


def _looks_like_phone(value: str) -> bool:
    digits = ''.join(c for c in (value or '') if c.isdigit())
    return len(digits) >= 10 and digits.startswith('09')


def user_display_name(user) -> str:
    """
    ترتیب: نام کامل معتبر → نام کاربری (برند/@handle) → موبایل → fallback.
    """
    if not user:
        return ''
    full = (user.get_full_name() or '').strip()
    if full and not _looks_like_phone(full):
        return full
    username = (user.username or '').strip()
    if username and not _looks_like_phone(username):
        return username
    phone = (getattr(user, 'phone', None) or '').strip()
    if phone:
        return phone
    if full:
        return full
    return username or 'مشاور'
