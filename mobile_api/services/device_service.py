"""ثبت دستگاه موبایل و اسلات لایسنس."""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from licenses.models import License, LicenseActivation
from licenses.services.security import normalize_hardware_fingerprint
from mobile_api.models import DEFAULT_NOTIFICATION_PREFS, MobileDevice
from mobile_api.services.license_service import license_payload_for_user
from workspace.services.access import _assigned_license_qs, _paid_license_qs


def _maybe_send_welcome_push(user, old_token: str, new_token: str) -> None:
    """First-time FCM registration — confirms push pipeline end-to-end."""
    if not (new_token or '').strip():
        return
    if (old_token or '').strip():
        return
    from mobile_api.services.push_service import send_welcome_push
    send_welcome_push(user)


def register_or_update_device(user, payload: Dict[str, Any]) -> Dict[str, Any]:
    device_id = normalize_hardware_fingerprint(payload.get('device_id', ''))
    if not device_id:
        raise ValueError('شناسه دستگاه نامعتبر است.')

    activation = _ensure_mobile_activation(user, device_id, payload)
    existing = MobileDevice.objects.filter(device_id=device_id).first()
    old_token = (existing.fcm_token or '') if existing else ''
    new_token = (payload.get('fcm_token') or '')[:512]

    prefs = DEFAULT_NOTIFICATION_PREFS.copy()
    with transaction.atomic():
        device, _ = MobileDevice.objects.update_or_create(
            device_id=device_id,
            defaults={
                'user': user,
                'device_model': (payload.get('device_model') or '')[:120],
                'os_version': (payload.get('os_version') or '')[:40],
                'app_version': (payload.get('app_version') or '')[:40],
                'fcm_token': new_token,
                'license_activation': activation,
                'last_seen_at': timezone.now(),
            },
        )
        if not device.notification_prefs:
            device.notification_prefs = prefs
            device.save(update_fields=['notification_prefs'])

    _maybe_send_welcome_push(user, old_token, new_token)

    return {
        'device_id': device.device_id,
        'registered_at': device.registered_at.isoformat(),
        'license': license_payload_for_user(user),
    }


def update_device_fcm(user, device_id: str, fcm_token: str) -> bool:
    device_id = normalize_hardware_fingerprint(device_id)
    token = (fcm_token or '')[:512]
    device = MobileDevice.objects.filter(user=user, device_id=device_id).first()
    old_token = (device.fcm_token or '') if device else ''
    updated = MobileDevice.objects.filter(user=user, device_id=device_id).update(
        fcm_token=token,
        last_seen_at=timezone.now(),
    )
    if updated and token:
        _maybe_send_welcome_push(user, old_token, token)
    return updated > 0


def _ensure_mobile_activation(
    user,
    device_id: str,
    payload: Dict[str, Any],
) -> Optional[LicenseActivation]:
    lic = (
        _paid_license_qs(user)
        .filter(status__in=['active', 'inactive'])
        .order_by('-created_at')
        .first()
    )
    if not lic:
        lic = (
            _assigned_license_qs(user)
            .order_by('-created_at')
            .first()
        )
    if not lic:
        return None

    label = (payload.get('device_model') or 'Android')[:80]
    existing = LicenseActivation.objects.filter(
        license=lic,
        hardware_fingerprint=device_id,
    ).first()
    if existing:
        existing.label = existing.label or f'موبایل: {label}'
        existing.is_active = True
        existing.save(update_fields=['label', 'is_active'])
        activation = existing
    else:
        active_count = LicenseActivation.objects.filter(license=lic, is_active=True).count()
        if active_count >= lic.max_activations:
            raise ValueError(
                f'حداکثر تعداد دستگاه ({lic.max_activations}) برای این لایسنس فعال شده است.',
            )
        activation = LicenseActivation.objects.create(
            license=lic,
            hardware_fingerprint=device_id,
            label=f'موبایل: {label}',
            is_active=True,
            notes='device_type=mobile',
        )
    if lic.status == 'inactive' and lic.can_be_activated():
        lic.status = 'active'
        lic.save(update_fields=['status'])
    return activation
