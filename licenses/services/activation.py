"""منطق مشترک فعال‌سازی/اتصال سخت‌افزار به لایسنس."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from licenses.models import AuditLog, License, LicenseActivation
from licenses.services.account_context import (
    build_license_account_payload,
    build_license_allocation_payload,
)
from licenses.services.security import get_client_ip


def _request_meta(request) -> dict:
    return getattr(request, 'META', {}) or {}


def _offline_grace_payload() -> dict:
    from datetime import timedelta

    from django.conf import settings

    hours = getattr(settings, 'LICENSE_OFFLINE_GRACE_HOURS', 72)
    grace_until = timezone.now() + timedelta(hours=hours)
    return {
        'offline_grace_until': grace_until.isoformat(),
        'offline_grace_hours': hours,
        'server_time': timezone.now().isoformat(),
    }


def _sync_license_expiration(license_obj: License) -> None:
    if license_obj.expires_at and license_obj.expires_at < timezone.now():
        if license_obj.status != 'expired':
            license_obj.status = 'expired'
            license_obj.save(update_fields=['status'])


def _refresh_license_status_after_deactivation(license_obj: License) -> None:
    if license_obj.status == 'active' and license_obj.active_slot_count() == 0:
        license_obj.status = 'inactive'
        license_obj.save(update_fields=['status'])


def _device_notes(device_type: str) -> str:
    dt = (device_type or 'desktop').strip().lower()
    if dt not in ('desktop', 'mobile', 'windows'):
        dt = 'desktop'
    if dt == 'windows':
        dt = 'desktop'
    return f'device_type={dt}'


@transaction.atomic
def bind_hardware_to_license(
    license_obj: License,
    hardware_fingerprint: str,
    request,
    *,
    device_label: str = '',
    device_type: str = 'desktop',
    audit_action: str = 'activation',
    audit_details: Optional[Dict[str, Any]] = None,
    account_user=None,
) -> Tuple[LicenseActivation, bool, Dict[str, Any]]:
    """
    اتصال fingerprint به لایسنس — atomic با select_for_update روی License.

    Returns: (activation, created, success_payload)
    """
    license_obj = License.objects.select_for_update(of=('self',)).select_related(
        'order__user', 'plan', 'assigned_user', 'assigned_by',
    ).get(pk=license_obj.pk)

    _sync_license_expiration(license_obj)
    license_obj.refresh_from_db()

    if not license_obj.can_be_activated():
        raise ValueError('لایسنس منقضی شده یا غیرفعال است.')

    meta = _request_meta(request)
    client_ip = get_client_ip(meta)
    notes = _device_notes(device_type)
    label = (device_label or '').strip()[:80]

    existing_active = LicenseActivation.objects.filter(
        license=license_obj,
        hardware_fingerprint=hardware_fingerprint,
        is_active=True,
    ).first()
    if existing_active:
        if label and not existing_active.label:
            existing_active.label = label
            existing_active.save(update_fields=['label'])
        payload = {
            'success': True,
            'message': 'لایسنس قبلاً برای این سیستم فعال شده است.',
            'license_key': license_obj.license_key,
            'license_id': license_obj.pk,
            'activated_at': existing_active.activated_at.isoformat(),
            'device_type': device_type if device_type != 'windows' else 'desktop',
            'account': build_license_account_payload(
                license_obj, account_user=account_user,
            ),
            'allocation': build_license_allocation_payload(
                license_obj, activation=existing_active,
            ),
            **_offline_grace_payload(),
            **license_obj.plan_payload(),
        }
        return existing_active, False, payload

    active_count = LicenseActivation.objects.filter(
        license=license_obj,
        is_active=True,
    ).count()
    if active_count >= license_obj.max_activations:
        raise ValueError(
            f'حداکثر تعداد سیستم ({license_obj.max_activations}) انجام شده است.',
        )

    total_slots = LicenseActivation.objects.filter(license=license_obj).count()
    if total_slots >= license_obj.max_activations:
        existing_slot = LicenseActivation.objects.filter(
            license=license_obj,
            hardware_fingerprint=hardware_fingerprint,
        ).first()
        if not existing_slot:
            raise ValueError(
                f'تمام اسلات‌های لایسنس ({license_obj.max_activations}) پر شده — '
                'ابتدا از داشبورد سیستم را ثبت کنید.',
            )

    defaults: Dict[str, Any] = {
        'ip_address': client_ip,
        'user_agent': meta.get('HTTP_USER_AGENT', ''),
        'is_active': True,
        'notes': notes,
    }
    if label:
        defaults['label'] = label

    activation, created = LicenseActivation.objects.get_or_create(
        license=license_obj,
        hardware_fingerprint=hardware_fingerprint,
        defaults=defaults,
    )
    if not created:
        activation.is_active = True
        activation.ip_address = client_ip
        activation.user_agent = meta.get('HTTP_USER_AGENT', '')
        if notes and not activation.notes:
            activation.notes = notes
        if label:
            activation.label = label
        activation.save(update_fields=[
            'is_active', 'ip_address', 'user_agent', 'notes', 'label',
        ])

    license_obj.status = 'active'
    license_obj.save(update_fields=['status'])

    details = {
        'hardware_fingerprint': hardware_fingerprint[:32],
        'reactivated': not created,
        'device_type': device_type if device_type != 'windows' else 'desktop',
    }
    if audit_details:
        details.update(audit_details)
    AuditLog.objects.create(
        license=license_obj,
        action_type=audit_action,
        ip_address=client_ip,
        user_agent=meta.get('HTTP_USER_AGENT', ''),
        details=details,
    )

    payload = {
        'success': True,
        'message': 'لایسنس با موفقیت فعال شد.',
        'license_key': license_obj.license_key,
        'license_id': license_obj.pk,
        'activated_at': activation.activated_at.isoformat(),
        'device_type': device_type if device_type != 'windows' else 'desktop',
        'account': build_license_account_payload(
            license_obj, account_user=account_user,
        ),
        'allocation': build_license_allocation_payload(license_obj, activation=activation),
        **_offline_grace_payload(),
        **license_obj.plan_payload(),
    }
    return activation, created, payload


def deactivate_hardware_from_license(
    license_obj: License,
    hardware_fingerprint: str,
    request,
    *,
    audit_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """غیرفعال‌سازی اسلات — atomic."""
    meta = _request_meta(request)
    client_ip = get_client_ip(meta)

    with transaction.atomic():
        license_obj = License.objects.select_for_update().get(pk=license_obj.pk)
        activation = LicenseActivation.objects.select_for_update().get(
            license=license_obj,
            hardware_fingerprint=hardware_fingerprint,
            is_active=True,
        )
        activation.is_active = False
        activation.save(update_fields=['is_active'])
        _refresh_license_status_after_deactivation(license_obj)

        details = {'hardware_fingerprint': hardware_fingerprint[:32]}
        if audit_details:
            details.update(audit_details)
        AuditLog.objects.create(
            license=license_obj,
            action_type='deactivation',
            ip_address=client_ip,
            user_agent=meta.get('HTTP_USER_AGENT', ''),
            details=details,
        )

    return {
        'success': True,
        'message': 'لایسنس با موفقیت غیرفعال شد.',
    }
