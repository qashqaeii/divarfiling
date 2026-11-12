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


def issue_licenses_for_paid_order(order: Order) -> list[License]:
    """
    صدور خودکار کلیدهای لایسنس پس از پرداخت — بدون نیاز به شناسه سخت‌افزار.
    idempotent: اگر لایسنس‌ها وجود داشته باشند همان‌ها را برمی‌گرداند.
    برای سفارش تمدید، همان کلید قبلی با تاریخ انقضای جدید به‌روز می‌شود.
    """
    if order.status != 'paid':
        return []

    from licenses.services.renewal_orders import (
        fulfill_multi_renewal_for_paid_order,
        order_has_renewal_items,
    )

    if order_has_renewal_items(order):
        renewed_list = fulfill_multi_renewal_for_paid_order(order)
        return renewed_list

    if order.renewal_license_id:
        from licenses.services.renewal import fulfill_renewal_for_paid_order

        renewed = fulfill_renewal_for_paid_order(order)
        return [renewed] if renewed else []

    target_count = max(1, int(order.quantity or 1))
    existing = list(
        License.objects.filter(order=order).order_by('sequence', 'pk')
    )
    if len(existing) >= target_count:
        return existing[:target_count]

    created: list[License] = []
    for sequence in range(len(existing) + 1, target_count + 1):
        license_obj = License.objects.create(
            order=order,
            sequence=sequence,
            license_key=generate_license_key(order, sequence=sequence),
            plan=order.plan,
            max_activations=order.plan.max_activations,
            expires_at=_license_expires_at(order.plan),
            status='inactive',
        )
        AuditLog.objects.create(
            license=license_obj,
            action_type='activation',
            details={
                'event': 'license_issued_on_payment',
                'plan': order.plan.name,
                'sequence': sequence,
                'quantity': target_count,
            },
        )
        created.append(license_obj)

    return existing + created


def issue_license_for_paid_order(order: Order) -> License | None:
    """سازگاری با کد قدیمی — اولین لایسنس سفارش را برمی‌گرداند."""
    licenses = issue_licenses_for_paid_order(order)
    return licenses[0] if licenses else None


def backfill_licenses_for_user(user) -> int:
    """صدور لایسنس برای سفارش‌های paid قدیمی که هنوز کلید ندارند."""
    created = 0
    orders = Order.objects.filter(user=user, status='paid').select_related('plan')
    for order in orders:
        before = License.objects.filter(order=order).count()
        issue_licenses_for_paid_order(order)
        after = License.objects.filter(order=order).count()
        if after > before:
            created += after - before
    return created


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


def claim_license_for_order(user, order_id, hardware_fingerprint: str = '', *, label: str = '') -> License:
    """
    بازیابی/صدور لایسنس برای سفارش paid.
    شناسه سخت‌افزار اختیاری است — فقط برای پیش‌ثبت اسلات در داشبورد.
    """
    try:
        order = Order.objects.select_related('plan', 'product').get(
            pk=order_id,
            user=user,
            status='paid',
        )
    except Order.DoesNotExist as exc:
        raise ValidationError('سفارش پرداخت‌شده یافت نشد.') from exc

    licenses = issue_licenses_for_paid_order(order)
    if not licenses:
        raise ValidationError('امکان صدور لایسنس برای این سفارش وجود ندارد.')

    license_obj = licenses[0]
    hw = (hardware_fingerprint or '').strip()
    if hw:
        _register_hardware(license_obj, hw)

    if label and hw:
        activation = LicenseActivation.objects.filter(
            license=license_obj,
            hardware_fingerprint=hw.strip().lower(),
        ).first()
        if activation and not activation.label:
            activation.label = label.strip()[:80]
            activation.save(update_fields=['label'])

    return license_obj
