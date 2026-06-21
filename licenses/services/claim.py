"""صدور لایسنس پس از خرید تأیید‌شده + ثبت شناسه سخت‌افزاری."""
from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from licenses.models import AuditLog, License, LicenseActivation
from licenses.utils import generate_license_key
from shop.models import Order


def _license_expires_at(plan):
    if plan and plan.duration_days:
        return timezone.now() + timedelta(days=int(plan.duration_days))
    return None


def _register_hardware(license_obj: License, hardware_fingerprint: str) -> None:
    hw = (hardware_fingerprint or '').strip().lower()
    if len(hw) < 8:
        raise ValidationError('شناسه سخت‌افزاری نامعتبر است.')

    if LicenseActivation.objects.filter(
        license=license_obj, hardware_fingerprint=hw,
    ).exists():
        return

    if license_obj.slots_used >= license_obj.max_activations:
        raise ValidationError(
            f'حداکثر تعداد سیستم ({license_obj.max_activations}) برای این لایسنس پر شده است.'
        )

    LicenseActivation.objects.create(
        license=license_obj,
        hardware_fingerprint=hw,
        is_active=False,
    )


def claim_license_for_order(user, order_id, hardware_fingerprint: str, *, label: str = '') -> License:
    """
    صدور (یا بازیابی) لایسنس برای سفارش paid و ثبت شناسه سخت‌افزار کاربر.
    """
    try:
        order = Order.objects.select_related('plan', 'product').get(
            pk=order_id,
            user=user,
            status='paid',
        )
    except Order.DoesNotExist as exc:
        raise ValidationError('سفارش پرداخت‌شده یافت نشد.') from exc

    existing = License.objects.filter(order=order).first()
    if existing:
        _register_hardware(existing, hardware_fingerprint)
        return existing

    license_obj = License.objects.create(
        order=order,
        license_key=generate_license_key(order),
        plan=order.plan,
        max_activations=order.plan.max_activations,
        expires_at=_license_expires_at(order.plan),
        status='inactive',
    )
    _register_hardware(license_obj, hardware_fingerprint)

    AuditLog.objects.create(
        license=license_obj,
        action_type='activation',
        details={
            'event': 'license_claimed',
            'hardware_fingerprint': hardware_fingerprint[:32],
            'plan': order.plan.name,
        },
    )
    return license_obj
