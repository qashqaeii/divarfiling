"""ثبت تبدیل و attribution سبک برای Automation مدیریت."""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import ManagementAutomationRecipient, UserDiscountIssuance


ATTRIBUTION_WINDOW_DAYS = 7
CONVERSION_TYPE_ATTRIBUTED = 'attributed_discount'
CONVERSION_TYPE_ASSOCIATED = 'associated_purchase'


def _order_already_attributed(order_id_str: str) -> bool:
    return ManagementAutomationRecipient.objects.filter(
        metadata__order_id=order_id_str,
        converted_at__isnull=False,
    ).exists()


def record_order_conversion(order) -> int:
    """
    پس از پرداخت موفق — converted_at گیرنده مرتبط را idempotent به‌روز می‌کند.
    هر سفارش حداکثر یک بار به یک Recipient نسبت داده می‌شود.
    """
    if order.status != 'paid' or not order.user_id:
        return 0

    order_id_str = str(order.pk)
    if _order_already_attributed(order_id_str):
        return 0

    paid_at = getattr(order, 'paid_at', None) or timezone.now()
    window_start = paid_at - timedelta(days=ATTRIBUTION_WINDOW_DAYS)

    with transaction.atomic():
        if _order_already_attributed(order_id_str):
            return 0

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
                rec = (
                    ManagementAutomationRecipient.objects.filter(
                        rule__key=issuance.source_rule,
                        user_id=order.user_id,
                        status=ManagementAutomationRecipient.Status.SENT,
                        sent_at__gte=window_start,
                        sent_at__lte=paid_at + timedelta(minutes=30),
                        converted_at__isnull=True,
                        execution__dry_run=False,
                    )
                    .select_for_update()
                    .order_by('-sent_at')
                    .first()
                )
                if rec:
                    rec.converted_at = paid_at
                    rec.conversion_type = CONVERSION_TYPE_ATTRIBUTED
                    meta = dict(rec.metadata or {})
                    meta['order_id'] = order_id_str
                    rec.metadata = meta
                    rec.save(update_fields=['converted_at', 'conversion_type', 'metadata'])
                    return 1

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
            .select_for_update()
            .order_by('-sent_at')
            .first()
        )
        if rec:
            rec.converted_at = paid_at
            rec.conversion_type = CONVERSION_TYPE_ASSOCIATED
            meta = dict(rec.metadata or {})
            meta['order_id'] = order_id_str
            rec.metadata = meta
            rec.save(update_fields=['converted_at', 'conversion_type', 'metadata'])
            return 1
    return 0
