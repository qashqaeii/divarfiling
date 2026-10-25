"""هویت نمایشی اعضای تالار."""
import re
import unicodedata

from accounts.phone_utils import normalize_phone
from community_forum.constants import RESERVED_DISPLAY_NAMES
from community_forum.models import ForumMember

_PHONE_IN_NAME = re.compile(r'0?9\d{9}')
_DIGIT_RUN = re.compile(r'\d{5,}')


def mask_phone(phone: str) -> str:
    p = normalize_phone(phone or '')
    if len(p) < 8:
        return '***'
    return f'{p[:4]}***{p[-4:]}'


def _valid_account_name(user) -> str:
    name = (user.get_full_name() or '').strip()
    if not name or len(name) < 2:
        return ''
    if _PHONE_IN_NAME.search(name.replace(' ', '')):
        return ''
    if name.isdigit():
        return ''
    return name


def validate_display_name(raw: str) -> tuple[str, str | None]:
    """برگرداند (نام پاک‌شده، پیام خطا)."""
    name = unicodedata.normalize('NFKC', (raw or '').strip())
    name = re.sub(r'\s+', ' ', name)
    if not name:
        return '', 'نام نمایشی نمی‌تواند خالی باشد.'
    if len(name) < 2:
        return '', 'نام نمایشی خیلی کوتاه است.'
    if len(name) > 64:
        return '', 'نام نمایشی حداکثر ۶۴ کاراکتر باشد.'
    lower = name.casefold()
    for reserved in RESERVED_DISPLAY_NAMES:
        if reserved.casefold() in lower or lower == reserved.casefold():
            return '', 'این نام نمایشی مجاز نیست.'
    if _PHONE_IN_NAME.search(name.replace(' ', '').replace('-', '')):
        return '', 'نام نمایشی نمی‌تواند شماره تماس باشد.'
    if _DIGIT_RUN.search(name):
        return '', 'نام نمایشی حاوی ارقام طولانی مجاز نیست.'
    return name, None


def member_display_label(member: ForumMember, *, user=None) -> str:
    user = user or member.user
    if member.display_name and member.display_name_approved:
        return member.display_name
    account_name = _valid_account_name(user)
    if account_name:
        return account_name
    return mask_phone(getattr(user, 'phone', '') or '')


def member_avatar_url(member: ForumMember) -> str:
    profile = getattr(member.user, 'profile', None)
    if profile and profile.avatar:
        try:
            return profile.avatar.url
        except Exception:
            return ''
    return ''
