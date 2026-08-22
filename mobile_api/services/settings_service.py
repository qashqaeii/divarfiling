"""تنظیمات پروفایل و اعلان."""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.core.files.uploadedfile import UploadedFile

from mobile_api.models import DEFAULT_NOTIFICATION_PREFS, MobileDevice
from mobile_api.serializers import user_to_dict


def get_profile(user, request=None) -> Dict[str, Any]:
    return {
        **user_to_dict(user, request=request),
        'timezone': 'Asia/Tehran',
    }


def update_profile(user, data: Dict[str, Any], request=None) -> Dict[str, Any]:
    if data.get('full_name'):
        parts = str(data['full_name']).strip().split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
    if data.get('phone'):
        user.phone = data['phone']
    user.save()
    return get_profile(user, request=request)


def update_profile_avatar(
    user,
    *,
    avatar: Optional[UploadedFile] = None,
    clear: bool = False,
    request=None,
) -> Dict[str, Any]:
    from accounts.models import UserProfile

    profile, _created = UserProfile.objects.get_or_create(user=user)
    if clear:
        if profile.avatar:
            profile.avatar.delete(save=False)
        profile.avatar = None
        profile.save(update_fields=['avatar'])
        return get_profile(user, request=request)
    if avatar is None:
        raise ValueError('فایل تصویر ارسال نشده است.')
    content_type = (getattr(avatar, 'content_type', '') or '').lower()
    if content_type and not content_type.startswith('image/'):
        raise ValueError('فقط فایل تصویر پذیرفته می‌شود.')
    if profile.avatar:
        profile.avatar.delete(save=False)
    profile.avatar = avatar
    profile.save(update_fields=['avatar'])
    return get_profile(user, request=request)


def get_notification_prefs(user, device_id: str = '') -> Dict[str, Any]:
    prefs = DEFAULT_NOTIFICATION_PREFS.copy()
    if device_id:
        dev = MobileDevice.objects.filter(user=user, device_id=device_id).first()
        if dev and dev.notification_prefs:
            stored = {k: v for k, v in (dev.notification_prefs or {}).items() if k in prefs}
            prefs.update(stored)
    return prefs


def update_notification_prefs(user, device_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    prefs = get_notification_prefs(user, device_id)
    allowed = set(DEFAULT_NOTIFICATION_PREFS.keys())
    prefs.update({k: data[k] for k in data if k in allowed})
    if device_id:
        MobileDevice.objects.filter(user=user, device_id=device_id).update(
            notification_prefs=prefs,
        )
    return prefs
