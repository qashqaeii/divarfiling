"""تشخیص اطلاعات حساس در متن پیام."""
import re
import unicodedata

from django.core.exceptions import ValidationError

_DIGIT_MAP = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')

_MOBILE_RE = re.compile(r'(?:\+98|0098|98|0)?9\d{9}')
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_CARD_RE = re.compile(r'\b\d{16}\b')
_URL_RE = re.compile(
    r'(https?://|www\.|t\.me/|telegram\.me/|wa\.me/|instagram\.com/|rubika\.ir/)',
    re.IGNORECASE,
)


def _normalize_digits(text: str) -> str:
    return unicodedata.normalize('NFKC', text).translate(_DIGIT_MAP)


def normalize_message_body(raw: str) -> str:
    text = unicodedata.normalize('NFKC', raw or '')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [ln.strip() for ln in text.split('\n')]
    return '\n'.join(lines).strip()


def check_message_pii(body: str) -> None:
    """در صورت تشخیص PII یا لینک، ValidationError."""
    normalized = _normalize_digits(body)
    compact = re.sub(r'[\s\-().]', '', normalized)

    if _MOBILE_RE.search(compact):
        raise ValidationError(
            'به‌دلیل حفظ حریم خصوصی، ارسال شماره موبایل در تالار مجاز نیست.',
            code='pii_phone',
        )
    if _EMAIL_RE.search(body):
        raise ValidationError('ارسال ایمیل در تالار مجاز نیست.', code='pii_email')
    if _CARD_RE.search(compact):
        raise ValidationError('ارسال شماره کارت در تالار مجاز نیست.', code='pii_card')
    if _URL_RE.search(body):
        raise ValidationError('ارسال لینک خارجی در نسخه فعلی تالار مجاز نیست.', code='pii_url')
