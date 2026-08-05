"""لایسنس دسکتاپ — eligible، bind و validate session (مبتنی بر حساب کاربری)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from licenses.models import AuditLog, License, LicenseActivation
from licenses.services.account_context import build_license_account_payload
from licenses.services.activation import (
    _offline_grace_payload,
    _sync_license_expiration,
    bind_hardware_to_license,
)
from licenses.services.security import (
    get_client_ip,
    normalize_hardware_fingerprint,
    validate_hardware_fingerprint_format,
)
from workspace.services.access import _assigned_license_qs, _paid_license_qs

User = get_user_model()

BINDABLE_STATES = frozenset({'available', 'assigned', 'active_on_this_device'})


class DesktopLicensingError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = 'ERROR',
        http_status: int = 400,
        payload: Optional[dict] = None,
    ):
        self.message = message
        self.code = code
        self.http_status = http_status
        self.payload = payload or {}
        super().__init__(message)


def _key_short(license_key: str) -> str:
    key = (license_key or '').strip()
    if len(key) <= 8:
        return key
    return key[-8:]


def _device_type_from_activation(activation: Optional[LicenseActivation]) -> str:
    if not activation:
        return 'desktop'
    notes = (activation.notes or '').lower()
    if 'device_type=mobile' in notes:
        return 'mobile'
    return 'desktop'


def _user_can_use_license(
    user,
    license_obj: License,
    activation: Optional[LicenseActivation] = None,
) -> bool:
    """آیا کاربر حق استفاده/bind این لایسنس را دارد؟"""
    if license_obj.order.user_id == user.id:
        if license_obj.assigned_user_id and license_obj.assigned_user_id != user.id:
            return False
        return True
    if license_obj.assigned_user_id == user.id:
        return True
    if activation and activation.assigned_user_id == user.id:
        return True
    seat = LicenseActivation.objects.filter(
        license=license_obj,
        assigned_user=user,
    ).exists()
    return seat


def _compute_eligibility_state(
    license_obj: License,
    hardware_fingerprint: str,
    *,
    access_context: str,
) -> str:
    """available | assigned | active_on_this_device | active_on_other_device | full"""
    license_obj.sync_expiration_status(save=True)
    if license_obj.status in ('suspended', 'expired'):
        return 'full'

    act_this = LicenseActivation.objects.filter(
        license=license_obj,
        hardware_fingerprint=hardware_fingerprint,
    ).first()
    if act_this and act_this.is_active:
        return 'active_on_this_device'

    active_count = license_obj.active_slot_count()
    if active_count >= license_obj.max_activations:
        if act_this and not act_this.is_active:
            pass
        else:
            return 'full'

    if access_context in ('member_assigned', 'member_seat'):
        if license_obj.max_activations == 1 and active_count >= 1:
            other = LicenseActivation.objects.filter(
                license=license_obj,
                is_active=True,
            ).exclude(hardware_fingerprint=hardware_fingerprint).exists()
            if other:
                return 'active_on_other_device'
        return 'assigned'

    if license_obj.assigned_user_id:
        return 'assigned'

    return 'available'


def _serialize_eligible(
    license_obj: License,
    state: str,
    hardware_fingerprint: str,
    *,
    access_context: str,
    viewer_user,
) -> Dict[str, Any]:
    activations = list(
        LicenseActivation.objects.filter(license=license_obj).order_by('activated_at', 'pk'),
    )
    slots_used = len(activations)
    active_count = sum(1 for a in activations if a.is_active)
    slots_available = max(0, license_obj.max_activations - active_count)

    act_this = next(
        (a for a in activations if a.hardware_fingerprint == hardware_fingerprint),
        None,
    )

    can_bind = state in BINDABLE_STATES and state != 'full'
    if state == 'active_on_other_device':
        can_bind = False
    if state in ('available', 'assigned') and slots_available <= 0 and not (
        act_this and act_this.is_active
    ):
        can_bind = False
        state = 'full'

    devices = []
    for act in activations:
        if not act.is_active:
            continue
        devices.append({
            'activation_id': act.pk,
            'label': act.display_name,
            'device_type': _device_type_from_activation(act),
            'is_this_device': act.hardware_fingerprint == hardware_fingerprint,
            'activated_at': act.activated_at.isoformat() if act.activated_at else None,
        })

    assigned_member = None
    if license_obj.assigned_user_id:
        u = license_obj.assigned_user
        assigned_member = {
            'id': u.pk,
            'username': u.username,
            'name': u.get_full_name() or u.username,
        }

    return {
        'license_id': license_obj.pk,
        'plan_name': license_obj.plan.name if license_obj.plan_id else '',
        'key_short': _key_short(license_obj.license_key),
        'expires_at': license_obj.expires_at.isoformat() if license_obj.expires_at else None,
        'status': license_obj.status,
        'allocation_state': access_context,
        'eligibility_state': state,
        'can_bind': can_bind,
        'max_activations': license_obj.max_activations,
        'slots_used': slots_used,
        'slots_active': active_count,
        'slots_available': slots_available,
        'assigned_member': assigned_member,
        'active_devices': devices,
        'is_owner': license_obj.order.user_id == viewer_user.id,
    }


def get_eligible_licenses(user, hardware_fingerprint: str) -> Dict[str, Any]:
    """لیست لایسنس‌های مجاز — بدون کلید کامل."""
    hw = normalize_hardware_fingerprint(hardware_fingerprint)
    if not validate_hardware_fingerprint_format(hw):
        raise DesktopLicensingError(
            'شناسه سخت‌افزاری نامعتبر است.',
            code='VALIDATION_ERROR',
        )

    seen: Set[int] = set()
    items: List[Dict[str, Any]] = []

    def _add(lic: License, context: str) -> None:
        if lic.pk in seen:
            return
        if not _user_can_use_license(user, lic):
            return
        state = _compute_eligibility_state(lic, hw, access_context=context)
        if lic.status in ('suspended', 'expired'):
            return
        if lic.expires_at and lic.expires_at < timezone.now():
            return
        seen.add(lic.pk)
        row = _serialize_eligible(lic, state, hw, access_context=context, viewer_user=user)
        items.append(row)

    for act in LicenseActivation.objects.filter(
        hardware_fingerprint=hw,
        is_active=True,
        license__order__status='paid',
    ).select_related('license', 'license__plan', 'license__order', 'license__assigned_user'):
        lic = act.license
        if _user_can_use_license(user, lic, act):
            ctx = 'owner' if lic.order.user_id == user.id else 'member_seat'
            if lic.assigned_user_id == user.id:
                ctx = 'member_assigned'
            _add(lic, ctx)

    for lic in _paid_license_qs(user).select_related('plan', 'order', 'assigned_user'):
        if lic.assigned_user_id and lic.assigned_user_id != user.id:
            continue
        _add(lic, 'owner')

    for lic in _assigned_license_qs(user).select_related('plan', 'order', 'assigned_user'):
        _add(lic, 'member_assigned')

    for act in LicenseActivation.objects.filter(
        assigned_user=user,
        license__order__status='paid',
    ).exclude(
        license__status__in=['suspended', 'expired'],
    ).filter(
        Q(license__expires_at__isnull=True) | Q(license__expires_at__gt=timezone.now()),
    ).select_related('license', 'license__plan', 'license__order', 'license__assigned_user'):
        _add(act.license, 'member_seat')

    items.sort(key=lambda x: (
        0 if x['eligibility_state'] == 'active_on_this_device' else 1,
        x['license_id'],
    ))

    active_here = [i for i in items if i['eligibility_state'] == 'active_on_this_device']
    bindable = [i for i in items if i.get('can_bind')]

    auto_bind_license_id: Optional[int] = None
    if active_here:
        auto_bind_license_id = active_here[0]['license_id']
    elif len(bindable) == 1:
        auto_bind_license_id = bindable[0]['license_id']

    return {
        'licenses': items,
        'auto_bind_license_id': auto_bind_license_id,
        'has_bindable': bool(bindable),
        'hardware_fingerprint': hw,
    }


def _get_license_for_bind(user, license_id: int) -> License:
    try:
        lic = License.objects.select_related('order', 'plan', 'assigned_user').get(
            pk=license_id,
            order__status='paid',
        )
    except License.DoesNotExist as exc:
        raise DesktopLicensingError(
            'لایسنس یافت نشد.',
            code='LICENSE_NOT_FOUND',
            http_status=404,
        ) from exc

    if not _user_can_use_license(user, lic):
        raise DesktopLicensingError(
            'دسترسی به این لایسنس ندارید.',
            code='LICENSE_FORBIDDEN',
            http_status=403,
        )
    return lic


def resolve_bind_license_id(
    user,
    hardware_fingerprint: str,
    license_id: Optional[int] = None,
) -> int:
    """انتخاب قطعی license_id برای bind."""
    eligible = get_eligible_licenses(user, hardware_fingerprint)
    licenses = eligible['licenses']
    bindable = [i for i in licenses if i.get('can_bind')]

    if not bindable:
        raise DesktopLicensingError(
            'لایسنس فعال یا قابل اتصال برای این حساب یافت نشد.',
            code='NO_ELIGIBLE_LICENSE',
            http_status=403,
        )

    if license_id is not None:
        _get_license_for_bind(user, license_id)
        return license_id

    auto_id = eligible.get('auto_bind_license_id')
    if auto_id is not None:
        return auto_id

    if len(bindable) == 1:
        return bindable[0]['license_id']

    raise DesktopLicensingError(
        'چند لایسنس قابل استفاده دارید — یکی را انتخاب کنید.',
        code='LICENSE_SELECTION_REQUIRED',
        http_status=409,
        payload={'licenses': licenses},
    )


def bind_desktop_device(
    user,
    hardware_fingerprint: str,
    request,
    *,
    license_id: Optional[int] = None,
    device_label: str = '',
) -> Dict[str, Any]:
    """اتصال دستگاه ویندوز به لایسنس — atomic."""
    hw = normalize_hardware_fingerprint(hardware_fingerprint)
    if not validate_hardware_fingerprint_format(hw):
        raise DesktopLicensingError(
            'شناسه سخت‌افزاری نامعتبر است.',
            code='VALIDATION_ERROR',
        )

    target_id = resolve_bind_license_id(user, hw, license_id)
    license_obj = _get_license_for_bind(user, target_id)

    meta = getattr(request, 'META', {}) or {}
    client_ip = get_client_ip(meta)

    try:
        with transaction.atomic():
            _activation, _created, payload = bind_hardware_to_license(
                license_obj,
                hw,
                request,
                device_label=device_label or 'Windows',
                device_type='windows',
                audit_action='activation',
                audit_details={
                    'event': 'desktop_account_bind',
                    'user_id': user.pk,
                    'username': user.username,
                },
            )
    except ValueError as exc:
        raise DesktopLicensingError(str(exc), code='BIND_FAILED') from exc

    AuditLog.objects.create(
        license=license_obj,
        action_type='activation',
        ip_address=client_ip,
        user_agent=meta.get('HTTP_USER_AGENT', ''),
        details={
            'event': 'desktop_bind',
            'user_id': user.pk,
            'hardware_fingerprint': hw[:32],
        },
    )
    payload['eligibility'] = get_eligible_licenses(user, hw)
    return payload


def validate_desktop_session(
    user,
    hardware_fingerprint: str,
    request,
    *,
    license_key: Optional[str] = None,
) -> Dict[str, Any]:
    """اعتبارسنجی session حساب + دستگاه."""
    hw = normalize_hardware_fingerprint(hardware_fingerprint)
    if not validate_hardware_fingerprint_format(hw):
        raise DesktopLicensingError(
            'شناسه سخت‌افزاری نامعتبر است.',
            code='VALIDATION_ERROR',
        )

    license_obj: Optional[License] = None
    activation: Optional[LicenseActivation] = None

    if license_key:
        from licenses.services.security import normalize_license_key

        key = normalize_license_key(license_key)
        try:
            license_obj = License.objects.select_related('order', 'plan').get(
                license_key=key,
            )
        except License.DoesNotExist:
            raise DesktopLicensingError(
                'لایسنس یافت نشد.',
                code='LICENSE_NOT_FOUND',
                http_status=404,
            )
        if not _user_can_use_license(user, license_obj):
            raise DesktopLicensingError(
                'دسترسی به این لایسنس لغو شده است.',
                code='LICENSE_REVOKED',
                http_status=403,
            )
        activation = LicenseActivation.objects.filter(
            license=license_obj,
            hardware_fingerprint=hw,
            is_active=True,
        ).first()
    else:
        for act in LicenseActivation.objects.filter(
            hardware_fingerprint=hw,
            is_active=True,
            license__order__status='paid',
        ).select_related('license', 'license__plan', 'license__order'):
            if _user_can_use_license(user, act.license, act):
                license_obj = act.license
                activation = act
                break

    if not license_obj or not activation:
        eligible = get_eligible_licenses(user, hw)
        return {
            'valid': False,
            'error': 'لایسنس روی این سیستم فعال نشده است.',
            'code': 'NOT_ACTIVATED_ON_DEVICE',
            'eligible': eligible,
        }

    _sync_license_expiration(license_obj)
    license_obj.refresh_from_db()

    is_valid = license_obj.is_valid() and activation.is_active
    error = None
    if not is_valid:
        if license_obj.status == 'expired':
            error = 'لایسنس منقضی شده است.'
        elif license_obj.status == 'suspended':
            error = 'لایسنس مسدود شده است.'
        elif not _user_can_use_license(user, license_obj, activation):
            error = 'دسترسی به این لایسنس لغو شده است.'
        else:
            error = 'لایسنس نامعتبر است.'

    meta = getattr(request, 'META', {}) or {}
    if is_valid:
        AuditLog.objects.create(
            license=license_obj,
            action_type='validation',
            ip_address=get_client_ip(meta),
            user_agent=meta.get('HTTP_USER_AGENT', ''),
            details={
                'event': 'desktop_session_validate',
                'user_id': user.pk,
                'hardware_fingerprint': hw[:32],
            },
        )

    payload: Dict[str, Any] = {
        'valid': is_valid,
        'license_id': license_obj.pk,
        'license_key': license_obj.license_key,
        'status': license_obj.status,
        'device_type': _device_type_from_activation(activation),
        **_offline_grace_payload(),
        **license_obj.plan_payload(),
    }
    if error:
        payload['error'] = error
        payload['code'] = 'LICENSE_INVALID'
    else:
        payload['account'] = build_license_account_payload(license_obj)
        payload['message'] = 'session معتبر است'
    payload['eligible'] = get_eligible_licenses(user, hw)
    return payload
