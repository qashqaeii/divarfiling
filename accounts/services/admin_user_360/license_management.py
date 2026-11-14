"""عملیات مدیریتی لایسنس از پرونده ۳۶۰ — فقط برای staff مجاز."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.services.admin_users_management import LICENSE_STATUS_LABELS
from licenses.models import AuditLog, License, LicenseActivation
from workspace.services.jalali_input import parse_jalali_datetime_string

VALID_LICENSE_STATUSES = {choice[0] for choice in License.STATUS_CHOICES}


def get_dossier_license_or_404(*, dossier_user_id: int, license_id: int) -> License:
    return get_object_or_404(
        License.objects.select_related('order', 'order__user', 'plan', 'assigned_user'),
        Q(order__user_id=dossier_user_id) | Q(assigned_user_id=dossier_user_id),
        pk=license_id,
    )


def _client_ip(meta: dict) -> Optional[str]:
    if not meta:
        return None
    forwarded = meta.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip() or None
    return meta.get('REMOTE_ADDR') or None


def _refresh_license_status_after_slots(license_obj: License) -> None:
    active = license_obj.activations.filter(is_active=True).exists()
    if active and license_obj.status == 'inactive':
        if license_obj.can_be_activated():
            license_obj.status = 'active'
            license_obj.save(update_fields=['status'])
    elif not active and license_obj.status == 'active':
        license_obj.status = 'inactive'
        license_obj.save(update_fields=['status'])


def _audit(
    license_obj: License,
    *,
    staff,
    action_type: str,
    details: Dict[str, Any],
    request_meta: Optional[dict] = None,
) -> None:
    AuditLog.objects.create(
        license=license_obj,
        action_type=action_type,
        ip_address=_client_ip(request_meta or {}),
        details={
            **details,
            'staff_id': staff.pk,
            'staff_username': staff.username,
            'source': 'admin_u360',
        },
    )


def _serialize_license_brief(license_obj: License) -> Dict[str, Any]:
    from accounts.services.admin_user_360.common import _jalali

    return {
        'id': license_obj.pk,
        'status': license_obj.status,
        'status_label': LICENSE_STATUS_LABELS.get(license_obj.status, license_obj.status),
        'max_activations': license_obj.max_activations,
        'slots_used': license_obj.activations.count(),
        'expires_jalali': _jalali(license_obj.expires_at) or 'نامحدود',
    }


@transaction.atomic
def apply_staff_license_action(
    *,
    dossier_user_id: int,
    license_id: int,
    staff,
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    request_meta: Optional[dict] = None,
) -> Dict[str, Any]:
    payload = payload or {}
    action = (action or '').strip().lower()
    license_obj = get_dossier_license_or_404(
        dossier_user_id=dossier_user_id,
        license_id=license_id,
    )
    license_obj = License.objects.select_for_update().select_related('plan', 'order').get(pk=license_obj.pk)

    if action == 'set_status':
        status = (payload.get('status') or '').strip().lower()
        if status not in VALID_LICENSE_STATUSES:
            raise ValueError('وضعیت لایسنس نامعتبر است.')
        prev = license_obj.status
        if prev == status:
            return {'license': _serialize_license_brief(license_obj), 'changed': False}
        license_obj.status = status
        license_obj.save(update_fields=['status'])
        _audit(
            license_obj,
            staff=staff,
            action_type='deactivation' if status in ('inactive', 'suspended', 'expired') else 'activation',
            details={
                'event': 'admin_u360_set_status',
                'previous_status': prev,
                'new_status': status,
            },
            request_meta=request_meta,
        )
        return {'license': _serialize_license_brief(license_obj), 'changed': True}

    if action == 'adjust_expiry':
        mode = (payload.get('mode') or 'add_days').strip().lower()
        if mode == 'set_datetime':
            raw = (payload.get('expires_jalali') or '').strip()
            if not raw:
                raise ValueError('تاریخ انقضا را انتخاب کنید.')
            parsed = parse_jalali_datetime_string(raw)
            if not parsed:
                raise ValueError('فرمت تاریخ شمسی نامعتبر است؛ نمونه: ۱۴۰۶/۰۷/۰۶ ۲۳:۰۷')
            prev = license_obj.expires_at
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            license_obj.expires_at = parsed
            license_obj.save(update_fields=['expires_at'])
            license_obj.sync_expiration_status(save=True)
            _audit(
                license_obj,
                staff=staff,
                action_type='activation',
                details={
                    'event': 'admin_u360_set_expiry',
                    'previous_expires_at': prev.isoformat() if prev else None,
                    'new_expires_at': license_obj.expires_at.isoformat() if license_obj.expires_at else None,
                },
                request_meta=request_meta,
            )
            return {'license': _serialize_license_brief(license_obj), 'changed': True}
        if mode == 'clear':
            prev = license_obj.expires_at
            license_obj.expires_at = None
            license_obj.save(update_fields=['expires_at'])
            license_obj.sync_expiration_status(save=True)
            _audit(
                license_obj,
                staff=staff,
                action_type='activation',
                details={
                    'event': 'admin_u360_clear_expiry',
                    'previous_expires_at': prev.isoformat() if prev else None,
                },
                request_meta=request_meta,
            )
            return {'license': _serialize_license_brief(license_obj), 'changed': True}
        try:
            days = int(payload.get('days', 0))
        except (TypeError, ValueError) as exc:
            raise ValueError('تعداد روز نامعتبر است.') from exc
        if days == 0:
            raise ValueError('تغییر انقضا باید غیر صفر باشد.')
        anchor = license_obj.expires_at or timezone.now()
        if anchor < timezone.now():
            anchor = timezone.now()
        license_obj.expires_at = anchor + timedelta(days=days)
        license_obj.save(update_fields=['expires_at'])
        license_obj.sync_expiration_status(save=True)
        _audit(
            license_obj,
            staff=staff,
            action_type='activation' if days > 0 else 'deactivation',
            details={
                'event': 'admin_u360_adjust_expiry',
                'days_delta': days,
                'new_expires_at': license_obj.expires_at.isoformat() if license_obj.expires_at else None,
            },
            request_meta=request_meta,
        )
        return {'license': _serialize_license_brief(license_obj), 'changed': True}

    if action == 'set_max_activations':
        try:
            new_max = int(payload.get('max_activations'))
        except (TypeError, ValueError) as exc:
            raise ValueError('تعداد اسلات نامعتبر است.') from exc
        if new_max < 1 or new_max > 50:
            raise ValueError('حداکثر اسلات باید بین ۱ تا ۵۰ باشد.')
        used = license_obj.activations.count()
        if new_max < used:
            raise ValueError(f'حداقل {used} اسلات ثبت‌شده دارد — ابتدا اسلات اضافه را حذف کنید.')
        prev = license_obj.max_activations
        if prev == new_max:
            return {'license': _serialize_license_brief(license_obj), 'changed': False}
        license_obj.max_activations = new_max
        license_obj.save(update_fields=['max_activations'])
        _audit(
            license_obj,
            staff=staff,
            action_type='transfer',
            details={
                'event': 'admin_u360_set_max_activations',
                'previous_max': prev,
                'new_max': new_max,
            },
            request_meta=request_meta,
        )
        return {'license': _serialize_license_brief(license_obj), 'changed': True}

    if action == 'set_activation_active':
        try:
            activation_id = int(payload.get('activation_id'))
        except (TypeError, ValueError) as exc:
            raise ValueError('شناسه اسلات نامعتبر است.') from exc
        active_flag = str(payload.get('is_active', '')).lower() in ('1', 'true', 'yes', 'on')
        try:
            activation = LicenseActivation.objects.select_for_update().get(
                pk=activation_id,
                license=license_obj,
            )
        except LicenseActivation.DoesNotExist as exc:
            raise ValueError('اسلات یافت نشد.') from exc
        if activation.is_active == active_flag:
            return {'license': _serialize_license_brief(license_obj), 'changed': False}
        activation.is_active = active_flag
        activation.save(update_fields=['is_active'])
        _refresh_license_status_after_slots(license_obj)
        _audit(
            license_obj,
            staff=staff,
            action_type='deactivation' if not active_flag else 'activation',
            details={
                'event': 'admin_u360_set_activation_active',
                'activation_id': activation.pk,
                'is_active': active_flag,
            },
            request_meta=request_meta,
        )
        return {'license': _serialize_license_brief(license_obj), 'changed': True}

    if action == 'remove_activation':
        try:
            activation_id = int(payload.get('activation_id'))
        except (TypeError, ValueError) as exc:
            raise ValueError('شناسه اسلات نامعتبر است.') from exc
        try:
            activation = LicenseActivation.objects.select_for_update().get(
                pk=activation_id,
                license=license_obj,
            )
        except LicenseActivation.DoesNotExist as exc:
            raise ValueError('اسلات یافت نشد.') from exc
        _audit(
            license_obj,
            staff=staff,
            action_type='deactivation',
            details={
                'event': 'admin_u360_remove_activation',
                'activation_id': activation.pk,
                'hardware_fingerprint': activation.hardware_fingerprint[:32],
                'was_active': activation.is_active,
            },
            request_meta=request_meta,
        )
        activation.delete()
        _refresh_license_status_after_slots(license_obj)
        return {'license': _serialize_license_brief(license_obj), 'changed': True}

    if action == 'revoke_assignment':
        if not license_obj.assigned_user_id:
            return {'license': _serialize_license_brief(license_obj), 'changed': False}
        prev_user = license_obj.assigned_user.username
        license_obj.assigned_user = None
        license_obj.assigned_by = None
        license_obj.assigned_at = None
        if license_obj.status not in ('suspended', 'expired'):
            license_obj.status = 'inactive'
        license_obj.save(update_fields=[
            'assigned_user', 'assigned_by', 'assigned_at', 'status',
        ])
        LicenseActivation.objects.filter(license=license_obj, is_active=True).update(is_active=False)
        _audit(
            license_obj,
            staff=staff,
            action_type='revoke',
            details={
                'event': 'admin_u360_revoke_assignment',
                'previous_user': prev_user,
            },
            request_meta=request_meta,
        )
        return {'license': _serialize_license_brief(license_obj), 'changed': True}

    raise ValueError('عملیات پشتیبانی‌نشده است.')