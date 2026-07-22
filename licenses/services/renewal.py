"""تمدید لایسنس موجود — بدون صدور کلید جدید."""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from licenses.models import AuditLog, License
from shop.models import Order


def evaluate_license_renewal(license_obj: License) -> tuple[bool, str]:
    """آیا لایسنس قابل تمدید است؟ (مجاز، پیام خطا)."""
    if license_obj.status == 'suspended':
        return False, 'این لایسنس مسدود شده و قابل تمدید نیست. با پشتیبانی تماس بگیرید.'

    product = license_obj.order.product
    if not product.is_active:
        return False, 'این محصول در حال حاضر فعال نیست.'

    if not license_obj.expires_at:
        return False, 'لایسنس نامحدود نیازی به تمدید ندارد.'

    return True, ''


def get_renewable_license_for_user(user, license_id: int) -> License:
    """لایسنس متعلق به کاربر که قابل تمدید است."""
    license_obj = get_object_or_404(
        License.objects.select_related('order', 'order__product', 'plan'),
        pk=license_id,
        order__user=user,
        order__status='paid',
    )
    ok, message = evaluate_license_renewal(license_obj)
    if not ok:
        raise Http404(message)
    return license_obj


def compute_renewed_expires_at(license_obj: License, plan) -> timezone.datetime | None:
    """تاریخ انقضای جدید — از max(الان، انقضای فعلی) + مدت پلن."""
    now = timezone.now()
    base = license_obj.expires_at or now
    if base < now:
        base = now
    duration_days = getattr(plan, 'duration_days', None)
    if duration_days:
        return base + timedelta(days=int(duration_days))
    return None


def _renewal_already_fulfilled(order: Order, license_obj: License) -> bool:
    return AuditLog.objects.filter(
        license=license_obj,
        details__event='license_renewed',
        details__order_id=str(order.pk),
    ).exists()


def _reactivate_status(license_obj: License) -> str:
    if license_obj.activations.exists():
        return 'active'
    return 'inactive'


def fulfill_renewal_for_paid_order(order: Order) -> License | None:
    """
    تمدید لایسنس پس از پرداخت — idempotent.
    کلید لایسنس ثابت می‌ماند؛ فقط انقضا و پلن به‌روز می‌شود.
    """
    if order.status != 'paid' or not order.renewal_license_id:
        return None

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        license_obj = License.objects.select_for_update().get(
            pk=locked_order.renewal_license_id,
        )

        if locked_order.user_id != license_obj.order.user_id:
            raise ValueError('سفارش تمدید به کاربر لایسنس تعلق ندارد.')

        if _renewal_already_fulfilled(locked_order, license_obj):
            return license_obj

        previous_expires = license_obj.expires_at
        previous_plan_id = license_obj.plan_id
        new_expires = compute_renewed_expires_at(license_obj, locked_order.plan)

        license_obj.plan = locked_order.plan
        license_obj.max_activations = locked_order.plan.max_activations
        license_obj.expires_at = new_expires
        if license_obj.status == 'expired':
            license_obj.status = _reactivate_status(license_obj)
        license_obj.save(update_fields=['plan', 'max_activations', 'expires_at', 'status'])

        AuditLog.objects.create(
            license=license_obj,
            action_type='activation',
            details={
                'event': 'license_renewed',
                'order_id': str(locked_order.pk),
                'plan': locked_order.plan.name,
                'previous_plan_id': previous_plan_id,
                'previous_expires_at': previous_expires.isoformat() if previous_expires else None,
                'new_expires_at': new_expires.isoformat() if new_expires else None,
            },
        )

        return license_obj
