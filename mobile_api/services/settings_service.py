"""تنظیمات پروفایل و اعلان."""
from __future__ import annotations

from typing import Any, Dict

from mobile_api.models import DEFAULT_NOTIFICATION_PREFS, MobileDevice
from mobile_api.serializers import user_to_dict


def get_profile(user) -> Dict[str, Any]:
    return {
        **user_to_dict(user),
        'timezone': 'Asia/Tehran',
    }


def update_profile(user, data: Dict[str, Any]) -> Dict[str, Any]:
    if data.get('full_name'):
        parts = str(data['full_name']).strip().split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
    if data.get('phone'):
        user.phone = data['phone']
    user.save()
    return get_profile(user)


def get_notification_prefs(user, device_id: str = '') -> Dict[str, Any]:
    prefs = DEFAULT_NOTIFICATION_PREFS.copy()
    if device_id:
        dev = MobileDevice.objects.filter(user=user, device_id=device_id).first()
        if dev and dev.notification_prefs:
            prefs.update(dev.notification_prefs)
    return prefs


def update_notification_prefs(user, device_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    prefs = get_notification_prefs(user, device_id)
    prefs.update({k: data[k] for k in data if k in prefs or k == 'digest_hour'})
    if device_id:
        MobileDevice.objects.filter(user=user, device_id=device_id).update(
            notification_prefs=prefs,
        )
    return prefs
