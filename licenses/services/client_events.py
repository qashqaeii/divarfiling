"""ثبت رویدادهای اپ کلاینت ویندوز (اولین اجرا و ...)."""
from __future__ import annotations

from django.db import IntegrityError, transaction

from licenses.models import ClientAppEvent, License, LicenseActivation
from licenses.services.security import (
    RateLimitExceeded,
    check_rate_limit,
    get_client_ip,
    normalize_hardware_fingerprint,
    normalize_license_key,
    validate_hardware_fingerprint_format,
    validate_license_key_format,
)


class ClientEventAPIError(Exception):
    def __init__(self, message: str, *, http_status: int = 400, payload: dict | None = None):
        self.message = message
        self.http_status = http_status
        self.payload = payload or {}
        super().__init__(message)


def _request_meta(request) -> dict:
    return getattr(request, 'META', {})


def record_client_event(request) -> dict:
    data = getattr(request, 'data', {}) or {}
    license_key = normalize_license_key(data.get('license_key', ''))
    hardware_fingerprint = normalize_hardware_fingerprint(data.get('hardware_fingerprint', ''))
    event_type = (data.get('event_type') or '').strip()
    app_version = (data.get('app_version') or '').strip()[:40]
    platform = (data.get('platform') or ClientAppEvent.Platform.WINDOWS).strip()[:20]

    if not license_key or not hardware_fingerprint:
        raise ClientEventAPIError('لایسنس و شناسه سخت‌افزاری الزامی است.', http_status=400)
    if not validate_license_key_format(license_key):
        raise ClientEventAPIError('فرمت کلید لایسنس نامعتبر است.', http_status=400)
    if not validate_hardware_fingerprint_format(hardware_fingerprint):
        raise ClientEventAPIError('شناسه سخت‌افزاری نامعتبر است.', http_status=400)

    allowed_types = {choice.value for choice in ClientAppEvent.EventType}
    if event_type not in allowed_types:
        raise ClientEventAPIError('نوع رویداد نامعتبر است.', http_status=400)

    meta = _request_meta(request)
    client_ip = get_client_ip(meta)
    try:
        check_rate_limit('client_event', client_ip)
    except RateLimitExceeded as exc:
        raise ClientEventAPIError(str(exc), http_status=429) from exc

    try:
        license_obj = License.objects.select_related('order__user', 'plan').get(license_key=license_key)
    except License.DoesNotExist:
        raise ClientEventAPIError('لایسنس معتبر نیست.', http_status=404) from None

    license_obj.sync_expiration_status(save=True)
    if not license_obj.is_valid():
        raise ClientEventAPIError('لایسنس منقضی یا غیرفعال است.', http_status=400)

    activation = LicenseActivation.objects.filter(
        license=license_obj,
        hardware_fingerprint=hardware_fingerprint,
        is_active=True,
    ).first()
    if activation is None:
        raise ClientEventAPIError('لایسنس روی این سیستم فعال نشده است.', http_status=403)

    user = license_obj.order.user
    created = False
    try:
        with transaction.atomic():
            _, created = ClientAppEvent.objects.get_or_create(
                license=license_obj,
                hardware_fingerprint=hardware_fingerprint,
                event_type=event_type,
                defaults={
                    'user': user,
                    'activation': activation,
                    'platform': platform,
                    'app_version': app_version,
                    'ip_address': client_ip,
                    'user_agent': meta.get('HTTP_USER_AGENT', '')[:500],
                },
            )
    except IntegrityError:
        created = False

    return {
        'success': True,
        'recorded': created,
        'event_type': event_type,
        'message': 'رویداد ثبت شد.' if created else 'رویداد قبلاً ثبت شده است.',
    }
