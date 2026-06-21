"""منطق API لایسنس — atomic، sync انقضا، audit."""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from licenses.models import AuditLog, License, LicenseActivation
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
    return getattr(request, 'META', {})


def _audit(license_obj, action_type, request, details=None):
    meta = _request_meta(request)
    AuditLog.objects.create(
        license=license_obj,
        action_type=action_type,
        ip_address=get_client_ip(meta),
        user_agent=meta.get('HTTP_USER_AGENT', ''),
        details=details or {},
    )


def _offline_grace_payload() -> dict:
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
                license_obj = License.objects.select_for_update().get(license_key=license_key)
            except License.DoesNotExist:
                _audit(None, 'suspicious', request, {
                    'license_key': license_key,
                    'error': 'لایسنس یافت نشد',
                })
                raise LicenseAPIError('لایسنس معتبر نیست.', http_status=404) from None

            _sync_license_expiration(license_obj)
            license_obj.refresh_from_db()

            if not license_obj.can_be_activated():
                raise LicenseAPIError('لایسنس منقضی شده یا غیرفعال است.', http_status=400)

            existing_active = LicenseActivation.objects.filter(
                license=license_obj,
                hardware_fingerprint=hardware_fingerprint,
                is_active=True,
            ).first()
            if existing_active:
                return {
                    'success': True,
                    'message': 'لایسنس قبلاً برای این سیستم فعال شده است.',
                    'license_key': license_obj.license_key,
                    'activated_at': existing_active.activated_at.isoformat(),
                    **_offline_grace_payload(),
                    **license_obj.plan_payload(),
                }

            active_count = LicenseActivation.objects.filter(
                license=license_obj,
                is_active=True,
            ).count()
            if active_count >= license_obj.max_activations:
                raise LicenseAPIError(
                    f'حداکثر تعداد سیستم ({license_obj.max_activations}) انجام شده است.',
                    http_status=400,
                )

            total_slots = LicenseActivation.objects.filter(license=license_obj).count()
            if total_slots >= license_obj.max_activations:
                existing_slot = LicenseActivation.objects.filter(
                    license=license_obj,
                    hardware_fingerprint=hardware_fingerprint,
                ).first()
                if not existing_slot:
                    raise LicenseAPIError(
                        f'تمام اسلات‌های لایسنس ({license_obj.max_activations}) پر شده — '
                        'ابتدا از داشبورد سیستم را ثبت کنید.',
                        http_status=400,
                    )

            activation, created = LicenseActivation.objects.get_or_create(
                license=license_obj,
                hardware_fingerprint=hardware_fingerprint,
                defaults={
                    'ip_address': client_ip,
                    'user_agent': meta.get('HTTP_USER_AGENT', ''),
                    'is_active': True,
                },
            )
            if not created:
                activation.is_active = True
                activation.ip_address = client_ip
                activation.user_agent = meta.get('HTTP_USER_AGENT', '')
                activation.save(update_fields=['is_active', 'ip_address', 'user_agent'])

            license_obj.status = 'active'
            license_obj.save(update_fields=['status'])

            _audit(license_obj, 'activation', request, {
                'hardware_fingerprint': hardware_fingerprint[:32],
                'reactivated': not created,
            })

            return {
                'success': True,
                'message': 'لایسنس با موفقیت فعال شد.',
                'license_key': license_obj.license_key,
                'activated_at': activation.activated_at.isoformat(),
                **_offline_grace_payload(),
                **license_obj.plan_payload(),
            }
    except LicenseAPIError:
        raise


def validate_license(request) -> dict:
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
        license_obj = License.objects.get(license_key=license_key)
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

    with transaction.atomic():
        try:
            license_obj = License.objects.select_for_update().get(license_key=license_key)
            activation = LicenseActivation.objects.select_for_update().get(
                license=license_obj,
                hardware_fingerprint=hardware_fingerprint,
                is_active=True,
            )
        except (License.DoesNotExist, LicenseActivation.DoesNotExist):
            raise LicenseAPIError('لایسنس یا فعال‌سازی یافت نشد.', http_status=404) from None

        activation.is_active = False
        activation.save(update_fields=['is_active'])
        _refresh_license_status_after_deactivation(license_obj)

        _audit(license_obj, 'deactivation', request, {
            'hardware_fingerprint': hardware_fingerprint[:32],
        })

    return {
        'success': True,
        'message': 'لایسنس با موفقیت غیرفعال شد.',
    }
