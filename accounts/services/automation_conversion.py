"""ثبت تبدیل و attribution سبک برای Automation مدیریت."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from accounts.models import ManagementAutomationRecipient, UserDiscountIssuance


ATTRIBUTION_WINDOW_DAYS = 7


def record_order_conversion(order) -> int:
    """
    پس از پرداخت موفق — converted_at گیرنده مرتبط را idempotent به‌روز می‌کند.
    Returns تعداد رکوردهای به‌روزشده.
    """
    if order.status != 'paid' or not order.user_id:
        return 0

    paid_at = getattr(order, 'paid_at', None) or timezone.now()
    window_start = paid_at - timedelta(days=ATTRIBUTION_WINDOW_DAYS)

    updated = 0
    discount_code_id = getattr(order, 'discount_code_id', None)

    if discount_code_id:
        issuance = (
            UserDiscountIssuance.objects.filter(
                user_id=order.user_id,
                discount_code_id=discount_code_id,
            )
            .order_by('-issued_at')
            .first()
        )
        if issuance and issuance.source_rule:
            qs = ManagementAutomationRecipient.objects.filter(
                rule__key=issuance.source_rule,
                user_id=order.user_id,
                status=ManagementAutomationRecipient.Status.SENT,
                sent_at__gte=window_start,
                sent_at__lte=paid_at + timedelta(minutes=30),
                converted_at__isnull=True,
                execution__dry_run=False,
            ).order_by('-sent_at')
            rec = qs.first()
            if rec:
                rec.converted_at = paid_at
                rec.conversion_type = 'attributed_discount'
                meta = dict(rec.metadata or {})
                meta['order_id'] = str(order.pk)
                rec.metadata = meta
                rec.save(update_fields=['converted_at', 'conversion_type', 'metadata'])
                updated += 1
                return updated

    # Association: هر ارسال موفق اخیر همان کاربر
    rec = (
        ManagementAutomationRecipient.objects.filter(
            user_id=order.user_id,
            status=ManagementAutomationRecipient.Status.SENT,
            sent_at__gte=window_start,
            sent_at__lte=paid_at + timedelta(minutes=30),
            converted_at__isnull=True,
            execution__dry_run=False,
        )
        .exclude(rule__action_type='management_alert')
        .order_by('-sent_at')
        .first()
    )
    if rec:
        rec.converted_at = paid_at
        rec.conversion_type = 'associated_purchase'
        meta = dict(rec.metadata or {})
        meta['order_id'] = str(order.pk)
        rec.metadata = meta
        rec.save(update_fields=['converted_at', 'conversion_type', 'metadata'])
        updated += 1
    return updated


def paid_orders_queryset(*, since=None, until=None):
    from shop.models import Order

    qs = Order.objects.filter(status='paid')
    if since:
        qs = qs.filter(paid_at__gte=since)
    if until:
        qs = qs.filter(paid_at__lte=until)
    return qs
