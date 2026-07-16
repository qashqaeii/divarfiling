"""نمایش محرمانه هویت کاربر در بخش‌های عمومی مرکز توسعه."""

from __future__ import annotations

MASK_SUFFIX = '****'
HIDDEN_TAIL = 4


def mask_identifier(value: str) -> str:
    """چهار نویسه آخر را مخفی می‌کند و **** جایگزین می‌شود."""
    text = (value or '').strip()
    if not text:
        return MASK_SUFFIX
    if len(text) <= HIDDEN_TAIL:
        return MASK_SUFFIX
    return f'{text[:-HIDDEN_TAIL]}{MASK_SUFFIX}'


def public_submitter_label(user) -> str:
    """نام کاربری ماسک‌شده؛ در غیر این صورت شماره تماس ماسک‌شده."""
    if user is None:
        return MASK_SUFFIX

    username = (getattr(user, 'username', None) or '').strip()
    if username:
        return mask_identifier(username)

    phone = (getattr(user, 'phone', None) or '').strip()
    if phone:
        return mask_identifier(phone)

    return MASK_SUFFIX
