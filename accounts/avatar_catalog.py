"""کاتالوگ آواتارهای پیش‌فرض و resolver مرکزی."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.templatetags.static import static

DEFAULT_AVATAR_KEY = 'avatar_01'

# avatar_01 … avatar_16 ↔ Avatar1.png … Avatar16.png در static/images/avatar/
AVATAR_KEYS: Tuple[str, ...] = tuple(f'avatar_{i:02d}' for i in range(1, 17))

# نوع مخاطب CRM → پسوند فایل در static/images/avatar/CONTACTAVATAR/{MAN|WOMAN}{Role}.webp
CONTACT_TYPE_AVATAR_ROLE: Dict[str, str] = {
    'خریدار': 'Buyer',
    'فروشنده': 'Seller',
    'سازنده': 'Builder',
    'مالک': 'Owner',
    'مستاجر': 'Tenant',
    'موجر': 'Landlord',
    'سرمایه‌گذار': 'Investor',
    'سرنخ': 'Lead',
    'متقاضی خرید': 'BuyerApplicant',
    'متقاضی اجاره': 'RentalApplicant',
    'فروشنده ملک': 'PropertySeller',
    'اشخاص حقوقی': 'CorporateEntity',
}
DEFAULT_CONTACT_AVATAR_ROLE = 'Lead'
CONTACT_AVATAR_STATIC_DIR = 'images/avatar/CONTACTAVATAR'


def normalize_avatar_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    raw = str(key).strip().lower().replace('-', '_')
    if raw in AVATAR_KEYS:
        return raw
    if raw.startswith('avatar') and raw[6:].isdigit():
        candidate = f'avatar_{int(raw[6:]):02d}'
        if candidate in AVATAR_KEYS:
            return candidate
    return None


def avatar_static_relative_path(key: str) -> str:
    """مسیر static نسبی (بدون ذخیره در DB)."""
    normalized = normalize_avatar_key(key) or DEFAULT_AVATAR_KEY
    index = AVATAR_KEYS.index(normalized) + 1
    return f'images/avatar/Avatar{index}.png'


def avatar_static_url(key: Optional[str] = None, request=None) -> str:
    rel = avatar_static_relative_path(normalize_avatar_key(key) or DEFAULT_AVATAR_KEY)
    url = static(rel)
    if request is not None:
        return request.build_absolute_uri(url)
    base = getattr(settings, 'STATIC_URL', '/static/') or '/static/'
    if url.startswith('http'):
        return url
    return f'{base.rstrip("/")}/{rel}'


def list_avatar_catalog(request=None) -> List[Dict[str, Any]]:
    items = []
    for key in AVATAR_KEYS:
        items.append({
            'key': key,
            'url': avatar_static_url(key, request=request),
        })
    return items


def _profile_has_custom_upload(profile) -> bool:
    if profile is None:
        return False
    avatar = getattr(profile, 'avatar', None)
    return bool(avatar and getattr(avatar, 'name', ''))


def resolve_user_avatar_display(profile, request=None) -> Dict[str, Any]:
    """
    اولویت: تصویر آپلود‌شده → avatar_key → پیش‌فرض avatar_01.
    """
    has_custom = _profile_has_custom_upload(profile)
    if has_custom:
        url = ''
        try:
            raw = profile.avatar.url
            url = request.build_absolute_uri(raw) if request else raw
        except Exception:
            url = ''
        stored_key = normalize_avatar_key(getattr(profile, 'avatar_key', None))
        return {
            'url': url,
            'avatar_key': stored_key,
            'has_custom_avatar': True,
            'effective_key': None,
        }

    stored_key = normalize_avatar_key(getattr(profile, 'avatar_key', None) if profile else None)
    effective_key = stored_key or DEFAULT_AVATAR_KEY
    return {
        'url': '',
        'avatar_key': stored_key,
        'has_custom_avatar': False,
        'effective_key': effective_key,
    }


def _contact_is_corporate(customer) -> bool:
    if getattr(customer, 'is_legal_entity', False):
        return True
    return (getattr(customer, 'customer_type', None) or '') == 'اشخاص حقوقی'


def contact_avatar_role_slug(customer) -> str:
    """پسوند نقش برای فایل آواتار مخاطب (مثلاً Buyer، Lead)."""
    if _contact_is_corporate(customer):
        return 'CorporateEntity'
    customer_type = getattr(customer, 'customer_type', None) or ''
    return CONTACT_TYPE_AVATAR_ROLE.get(customer_type, DEFAULT_CONTACT_AVATAR_ROLE)


def contact_avatar_gender_prefix(customer) -> str:
    """MAN یا WOMAN — بدون جنسیت یا شخص حقوقی → MAN."""
    if _contact_is_corporate(customer):
        return 'MAN'
    gender = getattr(customer, 'gender', None)
    if gender == 'female':
        return 'WOMAN'
    return 'MAN'


def contact_role_avatar_static_relative_path(customer) -> str:
    role = contact_avatar_role_slug(customer)
    prefix = contact_avatar_gender_prefix(customer)
    return f'{CONTACT_AVATAR_STATIC_DIR}/{prefix}{role}.webp'


def contact_role_avatar_url(customer, request=None) -> str:
    rel = contact_role_avatar_static_relative_path(customer)
    url = static(rel)
    if request is not None:
        return request.build_absolute_uri(url)
    base = getattr(settings, 'STATIC_URL', '/static/') or '/static/'
    if url.startswith('http'):
        return url
    return f'{base.rstrip("/")}/{rel}'


def resolve_contact_photo_url(customer, request=None) -> str:
    """URL تصویر اختصاصی مخاطب؛ خالی اگر ندارد."""
    photo = getattr(customer, 'photo', None)
    if not photo or not getattr(photo, 'name', ''):
        return ''
    try:
        raw = photo.url
        return request.build_absolute_uri(raw) if request else raw
    except Exception:
        return ''


def account_avatar_url_for_request(user, request=None) -> str:
    """URL نهایی آواتار حساب برای img (آپلود، preset یا پیش‌فرض)."""
    profile = getattr(user, 'profile', None)
    display = resolve_user_avatar_display(profile, request=request)
    if display['has_custom_avatar'] and display['url']:
        url = display['url']
        if request and url.startswith('/'):
            return request.build_absolute_uri(url)
        return url
    key = display.get('avatar_key') or DEFAULT_AVATAR_KEY
    rel = static(avatar_static_relative_path(key))
    if request:
        return request.build_absolute_uri(rel)
    return rel


def consultant_portrait_url(user, ws_settings=None, request=None) -> str:
    """
    عکس مشاور برای اشتراک/تنظیمات:
    consultant_photo → آواتار حساب (preset یا آپلود).
    """
    photo = getattr(ws_settings, 'consultant_photo', None) if ws_settings is not None else None
    if photo and getattr(photo, 'name', ''):
        try:
            raw = photo.url
            if request and raw.startswith('/'):
                return request.build_absolute_uri(raw)
            return raw
        except Exception:
            pass
    return account_avatar_url_for_request(user, request=request)


def resolve_contact_avatar_display(customer, request=None) -> Dict[str, Any]:
    """
    آواتار مخاطب CRM:
    ۱) تصویر اختصاصی (فیلد photo)
    ۲) آواتار پیش‌فرض نقش + جنسیت از CONTACTAVATAR
    """
    custom_url = resolve_contact_photo_url(customer, request=request)
    if custom_url:
        return {
            'photo_url': custom_url,
            'avatar_key': None,
            'has_photo': True,
        }
    role = contact_avatar_role_slug(customer)
    prefix = contact_avatar_gender_prefix(customer)
    avatar_key = f'contact_{prefix.lower()}_{role.lower()}'
    return {
        'photo_url': contact_role_avatar_url(customer, request=request),
        'avatar_key': avatar_key,
        'has_photo': False,
    }
