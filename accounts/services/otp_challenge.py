"""توکن کوتاه‌عمر پس از تأیید OTP — جایگزین session وب برای API موبایل."""
from __future__ import annotations

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

from accounts.phone_utils import normalize_phone

_SALT = 'mobile-otp-challenge-v1'
_MAX_AGE = 600  # ۱۰ دقیقه — هم‌تراز نشست وب پس از verify
_ALLOWED = frozenset({'register', 'password_reset'})


def _signer() -> TimestampSigner:
    return TimestampSigner(salt=_SALT)


def issue_verified_challenge(phone: str, purpose: str) -> str:
    purpose = (purpose or '').strip().lower()
    if purpose not in _ALLOWED:
        raise ValueError('purpose نامعتبر است.')
    payload = f'{normalize_phone(phone)}|{purpose}'
    return _signer().sign(payload)


def read_verified_challenge(token: str, expected_purpose: str, *, max_age: int = _MAX_AGE) -> str:
    """برمی‌گرداند شماره نرمال‌شده یا ValueError با پیام فارسی."""
    expected = (expected_purpose or '').strip().lower()
    if expected not in _ALLOWED:
        raise ValueError('نوع درخواست نامعتبر است.')
    if not (token or '').strip():
        raise ValueError('توکن تأیید نامعتبر است. دوباره کد را وارد کنید.')
    try:
        payload = _signer().unsign((token or '').strip(), max_age=max_age)
    except SignatureExpired:
        raise ValueError('زمان تأیید به پایان رسیده است. دوباره کد را درخواست کنید.')
    except BadSignature:
        raise ValueError('توکن تأیید نامعتبر است. دوباره کد را وارد کنید.')
    parts = str(payload).split('|', 1)
    if len(parts) != 2:
        raise ValueError('توکن تأیید نامعتبر است.')
    phone, purpose = parts
    if purpose != expected:
        raise ValueError('توکن تأیید با این مرحله سازگار نیست.')
    return normalize_phone(phone)
