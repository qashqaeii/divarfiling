"""منطق API لایسنس — atomic، sync انقضا، audit."""
from __future__ import annotations

from django.db import transaction

from licenses.models import License, LicenseActivation
from licenses.services.activation import (
    bind_hardware_to_license,
    deactivate_hardware_from_license,
)
from licenses.services.account_context import (
    build_license_account_payload,
    build_license_allocation_payload,
)
from licenses.services.security import (
    RateLimitExceeded,
    check_rate_limit,
    get_client_ip,
    normalize_hardware_fingerprint,
    normalize_license_key,
    validate_hardware_fingerprint_format,
    validate_license_key_format,
)


class LicenseAPIError(Exception):
    def __init__(self, message: str, *, http_status: int = 400, payload: dict | None = None):
        self.message = message
        self.http_status = http_status
        self.payload = payload or {}
        super().__init__(message)


def _request_meta(request) -> dict:
    return getattr(request, 'META', {}) or {}


def _audit(license_obj, action_type, request, details=None):
    from licenses.models import AuditLog

    meta = _request_meta(request)
    AuditLog.objects.create(
        license=license_obj,
        action_type=action_type,
        ip_address=get_client_ip(meta),
        user_agent=meta.get('HTTP_USER_AGENT', ''),
        details=details or {},
    )


def _parse_request(request):
    data = getattr(request, 'data', {}) or {}
    license_key = normalize_license_key(data.get('license_key', ''))
    hardware_fingerprint = normalize_hardware_fingerprint(data.get('hardware_fingerprint', ''))
    return license_key, hardware_fingerprint


def activate_license(request) -> dict:
    license_key, hardware_fingerprint = _parse_request(request)
    meta = _request_meta(request)
    client_ip = get_client_ip(meta)

    if not license_key or not hardware_fingerprint:
        raise LicenseAPIError('لایسنس و شناسه سخت‌افزاری الزامی است.', http_status=400)
    if not validate_license_key_format(license_key):
        raise LicenseAPIError('فرمت کلید لایسنس نامعتبر است.', http_status=400)
    if not validate_hardware_fingerprint_format(hardware_fingerprint):
        raise LicenseAPIError('شناسه سخت‌افزاری نامعتبر است.', http_status=400)

    try:
        check_rate_limit('activate', client_ip)
    except RateLimitExceeded as exc:
        raise LicenseAPIError(str(exc), http_status=429) from exc

    try:
        with transaction.atomic():
            try:
                license_obj = License.objects.select_for_update().select_related(
                    'order__user', 'plan', 'assigned_user', 'assigned_by',
                ).get(license_key=license_key)
            except License.DoesNotExist:
                _audit(None, 'suspicious', request, {
                    'license_key': license_key,
                    'error': 'لایسنس یافت نشد',
                })
                raise LicenseAPIError('لایسنس معتبر نیست.', http_status=404) from None

            try:
                _activation, _created, payload = bind_hardware_to_license(
                    license_obj,
                    hardware_fingerprint,
                    request,
                    device_type='desktop',
                    audit_action='activation',
                )
            except ValueError as exc:
                raise LicenseAPIError(str(exc), http_status=400) from exc

            return payload
    except LicenseAPIError:
        raise


def validate_license(request) -> dict:
    from django.utils import timezone

    from licenses.services.activation import _offline_grace_payload, _sync_license_expiration

    license_key, hardware_fingerprint = _parse_request(request)
    meta = _request_meta(request)
    client_ip = get_client_ip(meta)

    if not license_key or not hardware_fingerprint:
        raise LicenseAPIError('لایسنس و شناسه سخت‌افزاری الزامی است.', http_status=400)
    if not validate_license_key_format(license_key):
        raise LicenseAPIError('فرمت کلید لایسنس نامعتبر است.', http_status=400)
    if not validate_hardware_fingerprint_format(hardware_fingerprint):
        raise LicenseAPIError('شناسه سخت‌افزاری نامعتبر است.', http_status=400)

    try:
        check_rate_limit('validate', client_ip)
    except RateLimitExceeded as exc:
        raise LicenseAPIError(str(exc), http_status=429) from exc

    try:
        license_obj = License.objects.select_related(
            'order__user', 'plan', 'assigned_user', 'assigned_by',
        ).get(license_key=license_key)
    except License.DoesNotExist:
        raise LicenseAPIError('لایسنس یافت نشد.', http_status=404, payload={'valid': False})

    _sync_license_expiration(license_obj)
    license_obj.refresh_from_db()

    activation = LicenseActivation.objects.filter(
        license=license_obj,
        hardware_fingerprint=hardware_fingerprint,
        is_active=True,
    ).first()

    is_valid = license_obj.is_valid()
    is_activated = activation is not None
    is_ok = is_valid and is_activated

    error = None
    if not is_ok:
        if license_obj.status == 'expired' or (
            license_obj.expires_at and license_obj.expires_at < timezone.now()
        ):
            error = 'لایسنس منقضی شده است.'
        elif license_obj.status == 'suspended':
            error = 'لایسنس مسدود شده است.'
        elif not is_valid:
            error = 'لایسنس غیرفعال است.'
        elif not is_activated:
            error = 'لایسنس روی این سیستم فعال نشده است.'

    payload = {
        'valid': is_ok,
        'license_key': license_obj.license_key,
        'status': license_obj.status,
        'is_activated': is_activated,
        **_offline_grace_payload(),
        **license_obj.plan_payload(),
    }
    if error:
        payload['error'] = error

    if is_ok:
        payload['account'] = build_license_account_payload(license_obj)
        payload['allocation'] = build_license_allocation_payload(
            license_obj, activation=activation,
        )
        _audit(license_obj, 'validation', request, {'hardware_fingerprint': hardware_fingerprint[:32]})

    return payload


def deactivate_license(request) -> dict:
    license_key, hardware_fingerprint = _parse_request(request)
    meta = _request_meta(request)
    client_ip = get_client_ip(meta)

    if not license_key or not hardware_fingerprint:
        raise LicenseAPIError('لایسنس و شناسه سخت‌افزاری الزامی است.', http_status=400)
    if not validate_license_key_format(license_key):
        raise LicenseAPIError('فرمت کلید لایسنس نامعتبر است.', http_status=400)
    if not validate_hardware_fingerprint_format(hardware_fingerprint):
        raise LicenseAPIError('شناسه سخت‌افزاری نامعتبر است.', http_status=400)

    try:
        check_rate_limit('deactivate', client_ip)
    except RateLimitExceeded as exc:
        raise LicenseAPIError(str(exc), http_status=429) from exc

    try:
        license_obj = License.objects.get(license_key=license_key)
        return deactivate_hardware_from_license(
            license_obj,
            hardware_fingerprint,
            request,
        )
    except License.DoesNotExist:
        raise LicenseAPIError('لایسنس یا فعال‌سازی یافت نشد.', http_status=404) from None
    except LicenseActivation.DoesNotExist:
        raise LicenseAPIError('لایسنس یا فعال‌سازی یافت نشد.', http_status=404) from None
