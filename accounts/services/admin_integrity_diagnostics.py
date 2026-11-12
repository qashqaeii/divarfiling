"""Read-only financial integrity diagnostics for the management sales center.

Do not repair or mark orders as paid here. Counts represent all-time data,
not the selected sales date range. Categories may overlap.
"""
from __future__ import annotations

from urllib.parse import urlencode

from django.db.models import Count, Exists, F, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.urls import reverse

from licenses.models import License
from shop.models import Order, OrderRenewalItem
from shop.services.order_fulfillment_recovery import orders_needing_fulfillment_reconcile_qs


ISSUE_DEFINITIONS = (
    {
        'key': 'paid_missing_date',
        'title': 'پرداخت بدون تاریخ',
        'hint': 'سفارش paid است ولی paid_at ندارد؛ ممکن است در KPIهای بازه‌ای دیده نشود.',
        'severity': 'high',
    },
    {
        'key': 'complete_without_license',
        'title': 'تکمیل با کمبود کلید',
        'hint': 'خرید جدید با پرچم تکمیل، اما تعداد کلیدهای صادرشده کمتر از تعداد سفارش.',
        'severity': 'critical',
    },
    {
        'key': 'gateway_paid_order_unpaid',
        'title': 'عدم تطابق درگاه',
        'hint': 'تراکنش زیبال paid ثبت شده ولی سفارش paid نیست؛ نیازمند بررسی درگاه.',
        'severity': 'critical',
    },
    {
        'key': 'fulfillment_incomplete',
        'title': 'صدور یا تمدید ناقص',
        'hint': 'پرداخت موفق ثبت شده ولی عملیات تحویل هنوز تکمیل نشده است.',
        'severity': 'high',
    },
)


def financial_integrity_querysets():
    """Return lazily evaluated, reproducible exception cohorts."""
    issued_count = (
        License.objects.filter(order_id=OuterRef('pk'))
        .order_by()
        .values('order_id')
        .annotate(count=Count('pk'))
        .values('count')[:1]
    )
    multi_renewal = OrderRenewalItem.objects.filter(order_id=OuterRef('pk'))

    missing_date = Order.objects.filter(status='paid', paid_at__isnull=True)
    missing_entitlement = (
        Order.objects.filter(
            status='paid',
            fulfillment_status=Order.FulfillmentStatus.COMPLETE,
            renewal_license__isnull=True,
        )
        .alias(
            has_renewal_items=Exists(multi_renewal),
            issued_count=Coalesce(
                Subquery(issued_count, output_field=IntegerField()),
                Value(0),
            ),
        )
        .filter(has_renewal_items=False, issued_count__lt=F('quantity'))
    )
    gateway_mismatch = (
        Order.objects.filter(
            payment_method='zibal',
            transaction__status='paid',
        )
        .exclude(status='paid')
        .exclude(transaction__zibal_track_id__startswith='CARD-')
    )
    return {
        'paid_missing_date': missing_date,
        'complete_without_license': missing_entitlement,
        'gateway_paid_order_unpaid': gateway_mismatch,
        'fulfillment_incomplete': orders_needing_fulfillment_reconcile_qs(),
    }


def get_financial_integrity_context(*, selected: str = '', days: int = 30, limit: int = 5):
    """Summaries and a bounded diagnostic preview; no mutations/network calls."""
    cohorts = financial_integrity_querysets()
    selected = selected if selected in cohorts else ''
    range_value = 'all' if days == 0 else str(days)
    cards = []
    for spec in ISSUE_DEFINITIONS:
        key = spec['key']
        count = cohorts[key].count()
        href = (
            '#sales-queue-fulfillment'
            if key == 'fulfillment_incomplete'
            else reverse('admin_panel_sales') + '?' + urlencode({
                'days': range_value, 'audit': key,
            }) + '#sales-integrity'
        )
        cards.append({
            **spec,
            'count': count,
            'href': href,
            'active': selected == key,
        })

    rows = []
    if selected and selected != 'fulfillment_incomplete':
        rows = list(
            cohorts[selected]
            .select_related('user', 'plan')
            .order_by('created_at', 'pk')[:max(1, min(int(limit), 20))]
        )
    active_issue = next((card for card in cards if card['active']), None)
    return {
        'cards': cards,
        'total_flags': sum(item['count'] for item in cards),
        'selected': selected,
        'active_issue': active_issue,
        'rows': rows,
    }
