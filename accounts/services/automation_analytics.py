"""آمار عملکرد Automation مدیریت — درآمد و تبدیل."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from accounts.models import ManagementAutomationExecution, ManagementAutomationRecipient, ManagementAutomationRule
from accounts.services.automation_conversion import (
    ATTRIBUTION_WINDOW_DAYS,
    CONVERSION_TYPE_ASSOCIATED,
    CONVERSION_TYPE_ATTRIBUTED,
)


def _execution_sent_count(execution: ManagementAutomationExecution) -> int:
    if execution.dry_run:
        return ManagementAutomationRecipient.objects.filter(
            execution=execution,
            status=ManagementAutomationRecipient.Status.DRY_RUN,
        ).count()
    return ManagementAutomationRecipient.objects.filter(
        execution=execution,
        status=ManagementAutomationRecipient.Status.SENT,
    ).count()


def rule_stats_for_period(rule: ManagementAutomationRule, *, days: int = 30) -> dict:
    since = timezone.now() - timedelta(days=days)
    executions = ManagementAutomationExecution.objects.filter(
        rule=rule,
        started_at__gte=since,
        dry_run=False,
        status=ManagementAutomationExecution.Status.COMPLETED,
    )
    matched = sum(ex.matched_count for ex in executions)
    processed = sum(ex.processed_count for ex in executions)
    skipped = sum(ex.skipped_count for ex in executions)
    failed = sum(ex.failed_count for ex in executions)

    sent_recipients = ManagementAutomationRecipient.objects.filter(
        rule=rule,
        status=ManagementAutomationRecipient.Status.SENT,
        sent_at__gte=since,
        execution__dry_run=False,
    )
    sent = sent_recipients.count()
    unique_users = sent_recipients.values('user_id').distinct().count()

    attributed_recipients = sent_recipients.filter(
        converted_at__isnull=False,
        conversion_type=CONVERSION_TYPE_ATTRIBUTED,
    )
    associated_recipients = sent_recipients.filter(
        converted_at__isnull=False,
        conversion_type=CONVERSION_TYPE_ASSOCIATED,
    )

    attributed_orders = attributed_recipients.count()
    associated_orders = associated_recipients.count()

    attributed_order_ids = []
    for meta in attributed_recipients.values_list('metadata', flat=True):
        if isinstance(meta, dict) and meta.get('order_id'):
            attributed_order_ids.append(meta['order_id'])

    associated_order_ids = []
    for meta in associated_recipients.values_list('metadata', flat=True):
        if isinstance(meta, dict) and meta.get('order_id'):
            associated_order_ids.append(meta['order_id'])

    confirmed_revenue = Decimal('0')
    associated_revenue = Decimal('0')
    discount_used = Decimal('0')
    if attributed_order_ids:
        from shop.models import Order

        orders = Order.objects.filter(pk__in=attributed_order_ids, status='paid')
        confirmed_revenue = orders.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        discount_used = orders.aggregate(total=Sum('discount_amount'))['total'] or Decimal('0')
    if associated_order_ids:
        from shop.models import Order

        associated_revenue = (
            Order.objects.filter(pk__in=associated_order_ids, status='paid').aggregate(
                total=Sum('amount'),
            )['total']
            or Decimal('0')
        )

    converted_recipients = sent_recipients.filter(converted_at__isnull=False).count()
    conversion_rate = round(100 * attributed_orders / sent, 1) if sent else None

    return {
        'days': days,
        'matched': matched,
        'processed': processed,
        'skipped': skipped,
        'failed': failed,
        'sent': sent,
        'unique_recipients': unique_users,
        'associated_purchases': associated_orders,
        'attributed_purchases': attributed_orders,
        'converted_recipients': converted_recipients,
        'confirmed_revenue': int(confirmed_revenue),
        'associated_revenue': int(associated_revenue),
        'discount_consumed': int(discount_used),
        'conversion_rate': conversion_rate,
        'attribution_window_days': ATTRIBUTION_WINDOW_DAYS,
    }


def action_results_summary(*, days: int = 7) -> dict:
    since = timezone.now() - timedelta(days=days)
    executions = ManagementAutomationExecution.objects.filter(
        started_at__gte=since,
        dry_run=False,
        status=ManagementAutomationExecution.Status.COMPLETED,
    )
    messages = ManagementAutomationRecipient.objects.filter(
        execution__in=executions,
        status=ManagementAutomationRecipient.Status.SENT,
    ).count()

    converted = ManagementAutomationRecipient.objects.filter(
        execution__in=executions,
        converted_at__isnull=False,
    ).count()

    attributed_meta = ManagementAutomationRecipient.objects.filter(
        execution__in=executions,
        converted_at__isnull=False,
        conversion_type=CONVERSION_TYPE_ATTRIBUTED,
    ).values_list('metadata', flat=True)

    order_ids = []
    for meta in attributed_meta:
        if isinstance(meta, dict) and meta.get('order_id'):
            order_ids.append(meta['order_id'])

    confirmed_revenue = Decimal('0')
    if order_ids:
        from shop.models import Order

        confirmed_revenue = (
            Order.objects.filter(pk__in=order_ids, status='paid').aggregate(total=Sum('amount'))['total']
            or Decimal('0')
        )

    renewals = 0
    purchases = len(set(order_ids))
    if order_ids:
        from shop.models import Order

        renewals = Order.objects.filter(
            pk__in=order_ids,
            status='paid',
            renewal_license_id__isnull=False,
        ).count()

    return {
        'days': days,
        'messages_sent': messages,
        'automations_run': executions.count(),
        'purchases': purchases,
        'renewals': renewals,
        'attributed_conversions': converted,
        'confirmed_revenue': int(confirmed_revenue),
    }
