"""کاتالوگ آواتارهای پیش‌فرض و resolver مرکزی."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.templatetags.static import static

DEFAULT_AVATAR_KEY = 'avatar_01'

# avatar_01 … avatar_16 ↔ Avatar1.png … Avatar16.png در static/images/avatar/
AVATAR_KEYS: Tuple[str, ...] = tuple(f'avatar_{i:02d}' for i in range(1, 17))


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


def resolve_contact_avatar_display(customer, request=None) -> Dict[str, Any]:
    photo_url = resolve_contact_photo_url(customer, request=request)
    if photo_url:
        return {
            'photo_url': photo_url,
            'avatar_key': None,
            'effective_key': None,
            'uses_default_preset': False,
        }
    return {
        'photo_url': '',
        'avatar_key': None,
        'effective_key': DEFAULT_AVATAR_KEY,
        'uses_default_preset': True,
    }
