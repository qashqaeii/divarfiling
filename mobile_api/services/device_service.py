"""ثبت دستگاه موبایل و اسلات لایسنس."""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from licenses.models import License, LicenseActivation
from licenses.services.security import normalize_hardware_fingerprint
from mobile_api.models import DEFAULT_NOTIFICATION_PREFS, MobileDevice
from mobile_api.services.license_service import license_payload_for_user
from workspace.services.access import _assigned_license_qs, _owner_activatable_license_qs


def _maybe_send_welcome_push(user, old_token: str, new_token: str) -> None:
    """First-time FCM registration — یک welcome در inbox + FCM."""
    if not (new_token or '').strip():
        return
    if (old_token or '').strip():
        return
    from mobile_api.services.notification_service import maybe_create_welcome
    maybe_create_welcome(user)


def register_or_update_device(user, payload: Dict[str, Any]) -> Dict[str, Any]:
    device_id = normalize_hardware_fingerprint(payload.get('device_id', ''))
    if not device_id:
        raise ValueError('شناسه دستگاه نامعتبر است.')

    existing = MobileDevice.objects.filter(device_id=device_id).first()
    old_token = (existing.fcm_token or '') if existing else ''
    new_token = (payload.get('fcm_token') or '')[:512]

    prefs = DEFAULT_NOTIFICATION_PREFS.copy()
    with transaction.atomic():
        activation = _ensure_mobile_activation(user, device_id, payload)
        device, _ = MobileDevice.objects.update_or_create(
            device_id=device_id,
            defaults={
                'user': user,
                'device_model': (payload.get('device_model') or '')[:120],
                'os_version': (payload.get('os_version') or '')[:40],
                'app_version': (payload.get('app_version') or '')[:40],
                'fcm_token': new_token,
                'is_active': True,
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


def refresh_device_license_activation(user, device_id: str, payload: Dict[str, Any]) -> None:
    """پس از خرید یا تمدید — اگر دستگاه قبلاً ثبت شده بود، لایسنس را متصل می‌کند."""
    device_id = normalize_hardware_fingerprint(device_id)
    if not device_id:
        return
    device = MobileDevice.objects.filter(user=user, device_id=device_id).first()
    if not device:
        return
    if device.license_activation_id and device.license_activation and device.license_activation.is_active:
        lic = device.license_activation.license
        if lic.is_valid():
            return
    with transaction.atomic():
        activation = _ensure_mobile_activation(user, device_id, payload)
        if activation and device.license_activation_id != activation.pk:
            device.license_activation = activation
            device.last_seen_at = timezone.now()
            device.save(update_fields=['license_activation', 'last_seen_at'])


def update_device_fcm(user, device_id: str, fcm_token: str) -> bool:
    device_id = normalize_hardware_fingerprint(device_id)
    token = (fcm_token or '')[:512]
    device = MobileDevice.objects.filter(user=user, device_id=device_id).first()
    old_token = (device.fcm_token or '') if device else ''
    updated = MobileDevice.objects.filter(user=user, device_id=device_id).update(
        fcm_token=token,
        is_active=bool(token),
        last_seen_at=timezone.now(),
    )
    if updated and token:
        _maybe_send_welcome_push(user, old_token, token)
    return updated > 0


def deactivate_device(user, device_id: str) -> bool:
    """Logout — توکن FCM این دستگاه پاک می‌شود تا push حساب قبلی نرسد."""
    device_id = normalize_hardware_fingerprint(device_id or '')
    if not device_id:
        return False
    updated = MobileDevice.objects.filter(user=user, device_id=device_id).update(
        fcm_token='',
        is_active=False,
        last_seen_at=timezone.now(),
    )
    return updated > 0


def _pick_license_for_mobile_activation(user) -> Optional[License]:
    lic = (
        _owner_activatable_license_qs(user)
        .order_by('-created_at')
        .first()
    )
    if lic:
        return lic
    return _assigned_license_qs(user).order_by('-created_at').first()


def _ensure_mobile_activation(
    user,
    device_id: str,
    payload: Dict[str, Any],
) -> Optional[LicenseActivation]:
    lic = _pick_license_for_mobile_activation(user)
    if not lic:
        return None

    label = (payload.get('device_model') or 'Android')[:80]
    slot_label = f'موبایل: {label}'

    lic = License.objects.select_for_update(of=('self',)).get(pk=lic.pk)
    lic.sync_expiration_status(save=True)
    lic.refresh_from_db()

    if not lic.can_be_activated():
        return None

    existing = LicenseActivation.objects.filter(
        license=lic,
        hardware_fingerprint=device_id,
    ).first()
    if existing:
        update_fields = ['is_active']
        existing.is_active = True
        if not existing.label:
            existing.label = slot_label
            update_fields.append('label')
        existing.save(update_fields=update_fields)
        activation = existing
    else:
        active_count = LicenseActivation.objects.filter(
            license=lic,
            is_active=True,
        ).count()
        if active_count >= lic.max_activations:
            raise ValueError(
                f'حداکثر تعداد دستگاه ({lic.max_activations}) برای این لایسنس فعال شده است.',
            )
        activation, _created = LicenseActivation.objects.get_or_create(
            license=lic,
            hardware_fingerprint=device_id,
            defaults={
                'label': slot_label,
                'is_active': True,
                'notes': 'device_type=mobile',
            },
        )
        if not _created:
            activation.is_active = True
            if not activation.label:
                activation.label = slot_label
            activation.save(update_fields=['is_active', 'label'])

    if lic.status == 'inactive':
        lic.status = 'active'
        lic.save(update_fields=['status'])
    return activation
