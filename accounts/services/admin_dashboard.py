"""آمار و داده نمودار برای پنل مدیریت سیستم."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List

import jdatetime
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Exists, Max, OuterRef, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from workspace.services.jalali_input import to_persian_digits

from accounts.models import SmsMessageLog
from accounts.services.admin_exports import get_export_catalog
from accounts.services.admin_marketing import (
    SEGMENT_REGISTRY,
    get_marketing_dashboard_stats,
    get_recovery_flow_bridge_stats,
)
from accounts.services.admin_blog import get_blog_dashboard_stats
from accounts.services.admin_academy import get_academy_dashboard_stats
from accounts.services.admin_windows_app import (
    get_windows_activations,
    get_windows_app_stats,
    get_windows_download_logs,
    get_windows_first_launches,
    get_windows_user_funnel,
)
from accounts.services.pending_orders import PENDING_ORDER_STATUSES, get_pending_orders_for_display
from accounts.services.sms import get_sms_balance_snapshot

from affiliates.models import Affiliate, AffiliateSale, Withdrawal
from licenses.models import License, LicenseActivation
from shop.models import CardTransferSubmission, LicensePlan, Order, Product
from workspace.models import (
    CRMAgency,
    CRMAgencyMember,
    CRMDeal,
    CRMProperty,
    Customer,
    Dataset,
    Reminder,
    Ticket,
)

User = get_user_model()

TABLE_PREVIEW_ROWS = 5
TABLE_FETCH_LIMIT = 20

CHART_COLORS = [
    'rgba(124, 58, 237, 0.85)',
    'rgba(59, 130, 246, 0.8)',
    'rgba(16, 185, 129, 0.8)',
    'rgba(245, 158, 11, 0.85)',
    'rgba(239, 68, 68, 0.75)',
    'rgba(236, 72, 153, 0.75)',
    'rgba(14, 165, 233, 0.8)',
    'rgba(99, 102, 241, 0.8)',
]

ORDER_STATUS_LABELS = dict(Order.STATUS_CHOICES)
LICENSE_STATUS_LABELS = dict(License.STATUS_CHOICES)
PAYMENT_METHOD_LABELS = dict(Order.PAYMENT_METHOD_CHOICES)


def _today():
    return timezone.now().date()


def _date_range(days: int):
    end = _today()
    start = end - timedelta(days=days - 1)
    return start, end


def _chart_day_label(day, total_days: int) -> str:
    """برچسب شمسی برای محور نمودار."""
    j = jdatetime.date.fromgregorian(date=day)
    if total_days <= 7:
        return to_persian_digits(f'{j.day:02d}/{j.month:02d}')
    if total_days <= 31:
        return to_persian_digits(f'{j.day:02d}/{j.month:02d}')
    return to_persian_digits(f'{j.month:02d}/{j.year}')


def _fill_daily_series(start, end, rows, value_key='count', money=False, days: int = 30):
    """سری روزانه با صفر برای روزهای بدون داده."""
    lookup = {row['day']: row[value_key] for row in rows}
    labels, values = [], []
    current = start
    while current <= end:
        labels.append(_chart_day_label(current, days))
        val = lookup.get(current, 0)
        if money:
            val = int(val or 0)
        else:
            val = int(val or 0)
        values.append(val)
        current += timedelta(days=1)
    return labels, values


def _pct_change(current: int | float, previous: int | float) -> float | None:
    if previous in (0, None):
        return None if not current else 100.0
    return round(((current - previous) / previous) * 100, 1)


def get_system_start_at():
    """تاریخ شروع به کار سیستم = اولین لایسنس فعال‌شده."""
    first_active = (
        LicenseActivation.objects.filter(is_active=True)
        .order_by('activated_at')
        .values_list('activated_at', flat=True)
        .first()
    )
    if first_active:
        return first_active
    # اگر فعلاً هیچ اسلات فعالی نیست، اولین ثبت فعال‌سازی
    first_any = (
        LicenseActivation.objects.order_by('activated_at')
        .values_list('activated_at', flat=True)
        .first()
    )
    if first_any:
        return first_any
    # آخرین fallback: اولین لایسنس صادرشده
    return (
        License.objects.order_by('created_at')
        .values_list('created_at', flat=True)
        .first()
    )


def get_overview_stats() -> Dict[str, Any]:
    now = timezone.now()
    today = now.date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    system_start_at = get_system_start_at()
    system_uptime_days = None
    if system_start_at:
        start_local = timezone.localtime(system_start_at) if timezone.is_aware(system_start_at) else system_start_at
        system_uptime_days = max(0, (now.date() - start_local.date()).days)

    users_total = User.objects.count()
    users_active = User.objects.filter(is_active=True).count()
    users_new_week = User.objects.filter(date_joined__date__gte=week_ago).count()
    users_new_month = User.objects.filter(date_joined__date__gte=month_ago).count()

    orders_qs = Order.objects.all()
    orders_total = orders_qs.count()
    orders_paid = orders_qs.filter(status='paid').count()
    revenue_total = orders_qs.filter(status='paid').aggregate(
        total=Sum('amount'),
    )['total'] or Decimal(0)
    revenue_month = orders_qs.filter(
        status='paid', paid_at__date__gte=month_ago,
    ).aggregate(total=Sum('amount'))['total'] or Decimal(0)
    revenue_week = orders_qs.filter(
        status='paid', paid_at__date__gte=week_ago,
    ).aggregate(total=Sum('amount'))['total'] or Decimal(0)
    revenue_prev_month = orders_qs.filter(
        status='paid',
        paid_at__date__gte=month_ago - timedelta(days=30),
        paid_at__date__lt=month_ago,
    ).aggregate(total=Sum('amount'))['total'] or Decimal(0)

    licenses_total = License.objects.count()
    licenses_active = License.objects.filter(status='active').count()
    licenses_expired = License.objects.filter(status='expired').count()
    licenses_expiring_soon = License.objects.filter(
        status='active',
        expires_at__isnull=False,
        expires_at__lte=now + timedelta(days=14),
        expires_at__gt=now,
    ).count()
    activations_total = LicenseActivation.objects.filter(is_active=True).count()

    affiliates_total = Affiliate.objects.filter(is_active=True).count()
    affiliate_sales_total = AffiliateSale.objects.filter(status='paid').aggregate(
        total=Sum('commission_amount'),
    )['total'] or Decimal(0)

    pending_card_transfers = CardTransferSubmission.objects.filter(status='pending').count()
    pending_withdrawals = Withdrawal.objects.filter(status='pending').count()
    open_tickets = Ticket.objects.exclude(status='closed').count()
    unread_tickets = Ticket.objects.filter(staff_has_unread=True).exclude(status='closed').count()
    pending_orders = orders_qs.filter(status__in=PENDING_ORDER_STATUSES).count()
    users_pending_payment = User.objects.filter(
        orders__status__in=PENDING_ORDER_STATUSES,
    ).distinct().count()

    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    users_without_license = User.objects.filter(is_active=True).annotate(
        has_active_license=Exists(active_license_q),
    ).filter(has_active_license=False).count()

    datasets_total = Dataset.objects.count()

    return {
        'users_total': users_total,
        'users_active': users_active,
        'users_new_week': users_new_week,
        'users_new_month': users_new_month,
        'orders_total': orders_total,
        'orders_paid': orders_paid,
        'orders_pending': pending_orders,
        'users_pending_payment': users_pending_payment,
        'users_without_license': users_without_license,
        'revenue_total': int(revenue_total),
        'revenue_month': int(revenue_month),
        'revenue_week': int(revenue_week),
        'revenue_month_change': _pct_change(int(revenue_month), int(revenue_prev_month)),
        'licenses_total': licenses_total,
        'licenses_active': licenses_active,
        'licenses_expired': licenses_expired,
        'licenses_expiring_soon': licenses_expiring_soon,
        'activations_total': activations_total,
        'affiliates_total': affiliates_total,
        'affiliate_commissions_total': int(affiliate_sales_total),
        'pending_card_transfers': pending_card_transfers,
        'pending_withdrawals': pending_withdrawals,
        'open_tickets': open_tickets,
        'unread_tickets': unread_tickets,
        'datasets_total': datasets_total,
        'conversion_rate': round((orders_paid / users_total * 100), 1) if users_total else 0,
        'system_start_at': system_start_at,
        'system_uptime_days': system_uptime_days,
    }


def get_revenue_series(days: int = 30) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        Order.objects.filter(status='paid', paid_at__date__gte=start, paid_at__date__lte=end)
        .annotate(day=TruncDate('paid_at'))
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, value_key='total', money=True, days=days)
    return {'labels': labels, 'values': values}


def get_user_registration_series(days: int = 30) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        User.objects.filter(date_joined__date__gte=start, date_joined__date__lte=end)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return {'labels': labels, 'values': values}


def get_order_status_breakdown() -> List[Dict[str, Any]]:
    rows = Order.objects.values('status').annotate(count=Count('id')).order_by('-count')
    return [
        {
            'key': row['status'],
            'label': ORDER_STATUS_LABELS.get(row['status'], row['status']),
            'count': row['count'],
        }
        for row in rows
    ]


def get_payment_method_breakdown() -> List[Dict[str, Any]]:
    rows = (
        Order.objects.filter(status='paid')
        .values('payment_method')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('-total')
    )
    return [
        {
            'key': row['payment_method'],
            'label': PAYMENT_METHOD_LABELS.get(row['payment_method'], row['payment_method']),
            'count': row['count'],
            'total': int(row['total'] or 0),
        }
        for row in rows
    ]


def get_license_status_breakdown() -> List[Dict[str, Any]]:
    rows = License.objects.values('status').annotate(count=Count('id')).order_by('-count')
    return [
        {
            'key': row['status'],
            'label': LICENSE_STATUS_LABELS.get(row['status'], row['status']),
            'count': row['count'],
        }
        for row in rows
    ]


PLAN_TYPE_SHORT_LABELS = {
    'daily': 'آزمایشی ۱روزه',
    'monthly': 'لایسنس ۱ماهه',
    'quarterly': 'لایسنس ۳ماهه',
    'yearly': 'لایسنس ۱ساله',
}

PLAN_TYPE_ACCENTS = {
    'daily': 'emerald',
    'monthly': 'violet',
    'quarterly': 'blue',
    'yearly': 'amber',
}

PLAN_CHART_COLORS = [
    'rgba(16, 185, 129, 0.88)',
    'rgba(124, 58, 237, 0.88)',
    'rgba(59, 130, 246, 0.88)',
    'rgba(245, 158, 11, 0.88)',
    'rgba(6, 182, 212, 0.88)',
    'rgba(244, 63, 94, 0.88)',
]


def _plan_short_label(plan: LicensePlan) -> str:
    return PLAN_TYPE_SHORT_LABELS.get(
        plan.plan_type,
        plan.name.replace('لایسنس ', '').strip()[:18] or plan.name[:18],
    )


def get_plan_sales_breakdown(limit: int | None = None) -> List[Dict[str, Any]]:
    """فروش هر پلن — همه پلن‌های فعال؛ تجمیع فروش بر اساس نوع پلن (نه فقط plan_id)."""
    sales_by_type: Dict[tuple, Dict[str, int]] = {}
    sales_rows = (
        Order.objects.filter(status='paid', plan_id__isnull=False)
        .values('plan__product_id', 'plan__plan_type')
        .annotate(count=Count('id'), total=Sum('amount'))
    )
    for row in sales_rows:
        key = (row['plan__product_id'], row['plan__plan_type'] or '')
        bucket = sales_by_type.setdefault(key, {'count': 0, 'total': 0})
        bucket['count'] += int(row['count'] or 0)
        bucket['total'] += int(row['total'] or 0)

    plans_qs = (
        LicensePlan.objects.filter(is_active=True)
        .select_related('product')
        .order_by('order', 'price', 'id')
    )
    if limit:
        plans_qs = plans_qs[:limit]

    result: List[Dict[str, Any]] = []
    for plan in plans_qs:
        key = (plan.product_id, plan.plan_type or '')
        stats = sales_by_type.get(key, {'count': 0, 'total': 0})
        result.append({
            'plan_id': plan.id,
            'label': plan.name,
            'full_label': f'{plan.product.title} — {plan.name}',
            'short_label': _plan_short_label(plan),
            'plan_type': plan.plan_type,
            'accent': PLAN_TYPE_ACCENTS.get(plan.plan_type, 'violet'),
            'price': int(plan.price or 0),
            'count': stats['count'],
            'total': stats['total'],
        })
    return result


def build_plan_sales_chart_payload(plan_sales: List[Dict[str, Any]]) -> Dict[str, Any]:
    """نمودار افقی حرفه‌ای فروش پلن — ۴ پلن با رنگ اختصاصی."""
    colors = [
        PLAN_CHART_COLORS[i % len(PLAN_CHART_COLORS)]
        for i in range(len(plan_sales))
    ]
    return {
        'type': 'bar',
        'chartKind': 'plan_sales',
        'labels': [item['short_label'] for item in plan_sales],
        'fullLabels': [item['full_label'] for item in plan_sales],
        'orderCounts': [item['count'] for item in plan_sales],
        'planPrices': [item['price'] for item in plan_sales],
        'planTotals': [item['total'] for item in plan_sales],
        'accents': [item['accent'] for item in plan_sales],
        'datasets': [{
            'label': 'درآمد (تومان)',
            'data': [item['total'] for item in plan_sales],
            'backgroundColor': colors,
            'borderColor': [c.replace('0.88', '1') for c in colors],
            'borderWidth': 1,
            'borderRadius': 8,
            'borderSkipped': False,
            'barThickness': 32,
            'maxBarThickness': 40,
        }],
        'horizontal': True,
        'axis': 'money',
        'planCount': len(plan_sales),
    }


def get_product_revenue() -> List[Dict[str, Any]]:
    rows = (
        Order.objects.filter(status='paid')
        .values('product__title')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('-total')
    )
    return [
        {
            'label': row['product__title'],
            'count': row['count'],
            'total': int(row['total'] or 0),
        }
        for row in rows
    ]


def get_pending_orders(limit: int = TABLE_FETCH_LIMIT):
    return get_pending_orders_for_display(limit=limit)


def get_users_with_pending_orders(limit: int = TABLE_FETCH_LIMIT):
    return (
        User.objects.filter(orders__status__in=PENDING_ORDER_STATUSES)
        .annotate(
            pending_count=Count('orders', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
            pending_total=Sum('orders__amount', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
            last_pending=Max('orders__created_at', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
        )
        .distinct()
        .order_by('-last_pending')[:limit]
    )


def get_expiring_licenses(limit: int = TABLE_FETCH_LIMIT):
    now = timezone.now()
    return (
        License.objects.filter(
            status='active',
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=now + timedelta(days=14),
        )
        .select_related('order__user', 'plan')
        .order_by('expires_at')[:limit]
    )


def get_users_without_license_preview(limit: int = TABLE_FETCH_LIMIT):
    now = timezone.now()
    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return (
        User.objects.filter(is_active=True)
        .annotate(
            has_active_license=Exists(active_license_q),
            paid_orders=Count('orders', filter=Q(orders__status='paid')),
            pending_orders=Count('orders', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
        )
        .filter(has_active_license=False)
        .order_by('-date_joined')[:limit]
    )


def get_recent_orders(limit: int = TABLE_FETCH_LIMIT):
    return (
        Order.objects.select_related('user', 'product', 'plan')
        .order_by('-created_at')[:limit]
    )


def get_recent_users(limit: int = TABLE_FETCH_LIMIT):
    return User.objects.order_by('-date_joined')[:limit]


def get_pending_card_transfers(limit: int = TABLE_FETCH_LIMIT):
    return (
        CardTransferSubmission.objects.filter(status='pending')
        .select_related('order', 'order__user', 'order__product')
        .order_by('-created_at')[:limit]
    )


def get_open_tickets(limit: int = TABLE_FETCH_LIMIT):
    return (
        Ticket.objects.exclude(status='closed')
        .select_related('user')
        .order_by('-staff_has_unread', '-last_message_at', '-created_at')[:limit]
    )


def get_pending_withdrawals(limit: int = TABLE_FETCH_LIMIT):
    return (
        Withdrawal.objects.filter(status='pending')
        .select_related('wallet', 'wallet__user')
        .order_by('-created_at')[:limit]
    )


def build_charts_payload(days: int = 30) -> Dict[str, Any]:
    revenue = get_revenue_series(days)
    orders = get_order_count_series(days)
    signups = get_user_registration_series(days)
    order_status = get_order_status_breakdown()
    license_status = get_license_status_breakdown()
    payment_methods = get_payment_method_breakdown()
    plan_sales = get_plan_sales_breakdown()
    product_revenue = get_product_revenue()

    aov_values = []
    for rev, cnt in zip(revenue['values'], orders['values']):
        aov_values.append(int(rev / cnt) if cnt else 0)

    paid_users = User.objects.filter(orders__status='paid').distinct().count()
    revenue_total = int(Order.objects.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0)
    ltv = int(revenue_total / paid_users) if paid_users else 0
    users_total = User.objects.count()
    orders_paid = Order.objects.filter(status='paid').count()
    conversion = round((orders_paid / users_total * 100), 1) if users_total else 0

    return {
        'revenue_analytics': {
            'type': 'combo',
            'labels': revenue['labels'],
            'datasets': [
                {
                    'label': 'درآمد (تومان)',
                    'data': revenue['values'],
                    'type': 'line',
                    'borderColor': 'rgba(16, 185, 129, 1)',
                    'backgroundColor': 'rgba(16, 185, 129, 0.12)',
                    'fill': True,
                    'tension': 0.4,
                    'yAxisID': 'y',
                },
                {
                    'label': 'تعداد سفارش',
                    'data': orders['values'],
                    'type': 'bar',
                    'backgroundColor': 'rgba(124, 58, 237, 0.55)',
                    'borderRadius': 4,
                    'yAxisID': 'y1',
                },
                {
                    'label': 'میانگین سفارش (AOV)',
                    'data': aov_values,
                    'type': 'line',
                    'borderColor': 'rgba(245, 158, 11, 1)',
                    'backgroundColor': 'transparent',
                    'borderDash': [4, 4],
                    'tension': 0.35,
                    'yAxisID': 'y',
                },
            ],
            'axis': 'money',
            'metrics': {
                'aov': int(Order.objects.filter(status='paid').aggregate(avg=Avg('amount'))['avg'] or 0),
                'ltv': ltv,
                'conversion_rate': conversion,
            },
        },
        'revenue_trend': {
            'type': 'line',
            'labels': revenue['labels'],
            'datasets': [{
                'label': 'درآمد (تومان)',
                'data': revenue['values'],
                'borderColor': 'rgba(124, 58, 237, 1)',
                'backgroundColor': 'rgba(124, 58, 237, 0.12)',
                'fill': True,
                'tension': 0.35,
            }],
            'axis': 'money',
        },
        'user_signups': {
            'type': 'line',
            'labels': signups['labels'],
            'datasets': [{
                'label': 'ثبت‌نام جدید',
                'data': signups['values'],
                'borderColor': 'rgba(59, 130, 246, 1)',
                'backgroundColor': 'rgba(59, 130, 246, 0.15)',
                'fill': True,
                'tension': 0.35,
            }],
            'axis': 'count',
        },
        'user_retention': {
            'type': 'doughnut',
            'labels': ['کاربران بازگشتی ۳۰روز', 'کاربران جدید', 'بدون لایسنس'],
            'datasets': [{
                'data': [
                    max(0, User.objects.filter(
                        is_active=True,
                        last_login__gte=timezone.now() - timedelta(days=30),
                        date_joined__lt=timezone.now() - timedelta(days=30),
                    ).count()),
                    User.objects.filter(date_joined__gte=timezone.now() - timedelta(days=30)).count(),
                    User.objects.filter(is_active=True).annotate(
                        has_active_license=Exists(
                            License.objects.filter(
                                order__user=OuterRef('pk'),
                                status='active',
                            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
                        ),
                    ).filter(has_active_license=False).count(),
                ],
                'backgroundColor': [
                    'rgba(16, 185, 129, 0.85)',
                    'rgba(59, 130, 246, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                ],
            }],
            'axis': 'count',
        },
        'order_status': {
            'type': 'doughnut',
            'labels': [item['label'] for item in order_status],
            'datasets': [{
                'data': [item['count'] for item in order_status],
                'backgroundColor': CHART_COLORS[:len(order_status)],
            }],
            'axis': 'count',
        },
        'license_status': {
            'type': 'doughnut',
            'labels': [item['label'] for item in license_status],
            'datasets': [{
                'data': [item['count'] for item in license_status],
                'backgroundColor': CHART_COLORS[:len(license_status)],
            }],
            'axis': 'count',
        },
        'payment_methods': {
            'type': 'bar',
            'labels': [item['label'] for item in payment_methods],
            'datasets': [{
                'label': 'تعداد سفارش',
                'data': [item['count'] for item in payment_methods],
                'backgroundColor': 'rgba(16, 185, 129, 0.75)',
                'borderRadius': 6,
            }],
            'axis': 'count',
        },
        'plan_sales': build_plan_sales_chart_payload(plan_sales),
        'user_analytics': {
            'type': 'line',
            'labels': signups['labels'],
            'datasets': [
                {
                    'label': 'ثبت‌نام جدید',
                    'data': signups['values'],
                    'borderColor': 'rgba(59, 130, 246, 1)',
                    'backgroundColor': 'rgba(59, 130, 246, 0.15)',
                    'fill': True,
                    'tension': 0.35,
                },
            ],
            'axis': 'count',
        },
        'sales_trend': {
            'type': 'bar',
            'labels': orders['labels'],
            'datasets': [{
                'label': 'سفارش پرداخت‌شده',
                'data': orders['values'],
                'backgroundColor': 'rgba(6, 182, 212, 0.75)',
                'borderRadius': 6,
            }],
            'axis': 'count',
        },
        'crm_growth': {
            'type': 'doughnut',
            'labels': ['مخاطب', 'ملک', 'معامله', 'یادآور'],
            'datasets': [{
                'data': [
                    Customer.objects.count(),
                    CRMProperty.objects.count(),
                    CRMDeal.objects.count(),
                    Reminder.objects.count(),
                ],
                'backgroundColor': CHART_COLORS[:4],
            }],
            'axis': 'count',
        },
        'operations_gauge': {
            'type': 'doughnut',
            'labels': ['SMS موفق', 'SMS ناموفق'],
            'datasets': [{
                'data': [
                    SmsMessageLog.objects.filter(status__in=('sent', 'fake')).count(),
                    SmsMessageLog.objects.filter(status='failed').count(),
                ],
                'backgroundColor': ['rgba(16, 185, 129, 0.85)', 'rgba(239, 68, 68, 0.75)'],
            }],
            'axis': 'count',
        },
        'kpi_sparklines': {
            'revenue': _revenue_sparkline(7),
            'orders': _orders_sparkline(7),
            'signups': _signups_sparkline(7),
            'licenses': _licenses_sparkline(7),
        },
        'product_revenue': {
            'type': 'bar',
            'labels': [item['label'] for item in product_revenue],
            'datasets': [{
                'label': 'درآمد (تومان)',
                'data': [item['total'] for item in product_revenue],
                'backgroundColor': 'rgba(99, 102, 241, 0.8)',
                'borderRadius': 6,
            }],
            'axis': 'money',
        },
    }


def get_yesterday_stats() -> Dict[str, Any]:
    """آمار دیروز برای مقایسه KPI."""
    yesterday = _today() - timedelta(days=1)
    orders_paid_yesterday = Order.objects.filter(status='paid', paid_at__date=yesterday)
    return {
        'revenue_yesterday': int(orders_paid_yesterday.aggregate(total=Sum('amount'))['total'] or 0),
        'orders_paid_yesterday': orders_paid_yesterday.count(),
        'signups_yesterday': User.objects.filter(date_joined__date=yesterday).count(),
    }


def get_today_stats() -> Dict[str, Any]:
    """آمار امروز برای کارت‌های Spotlight."""
    today = _today()
    orders_paid_today = Order.objects.filter(status='paid', paid_at__date=today)
    paid_users = User.objects.filter(orders__status='paid').distinct().count()
    revenue_total = int(Order.objects.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0)
    return {
        'revenue_today': int(orders_paid_today.aggregate(total=Sum('amount'))['total'] or 0),
        'orders_paid_today': orders_paid_today.count(),
        'signups_today': User.objects.filter(date_joined__date=today).count(),
        'avg_order_value': int(
            Order.objects.filter(status='paid').aggregate(avg=Avg('amount'))['avg'] or 0
        ),
        'ltv': int(revenue_total / paid_users) if paid_users else 0,
        'orders_failed_today': Order.objects.filter(status='failed', created_at__date=today).count(),
    }


def get_users_online_count(minutes: int = 15) -> int:
    threshold = timezone.now() - timedelta(minutes=minutes)
    return User.objects.filter(is_active=True, last_login__gte=threshold).count()


def get_order_count_series(days: int = 30) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        Order.objects.filter(status='paid', paid_at__date__gte=start, paid_at__date__lte=end)
        .annotate(day=TruncDate('paid_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return {'labels': labels, 'values': values}


def _sparkline_values(days: int, rows, value_key: str = 'count', money: bool = False) -> List[int]:
    start, end = _date_range(days)
    _, values = _fill_daily_series(start, end, rows, value_key=value_key, money=money, days=days)
    return values


def _revenue_sparkline(days: int = 7) -> List[int]:
    start, end = _date_range(days)
    rows = (
        Order.objects.filter(status='paid', paid_at__date__gte=start, paid_at__date__lte=end)
        .annotate(day=TruncDate('paid_at'))
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )
    return _sparkline_values(days, rows, value_key='total', money=True)


def _orders_sparkline(days: int = 7) -> List[int]:
    start, end = _date_range(days)
    rows = (
        Order.objects.filter(status='paid', paid_at__date__gte=start, paid_at__date__lte=end)
        .annotate(day=TruncDate('paid_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    return _sparkline_values(days, rows)


def _signups_sparkline(days: int = 7) -> List[int]:
    start, end = _date_range(days)
    rows = (
        User.objects.filter(date_joined__date__gte=start, date_joined__date__lte=end)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    return _sparkline_values(days, rows)


def _licenses_sparkline(days: int = 7) -> List[int]:
    start, end = _date_range(days)
    rows = (
        License.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    return _sparkline_values(days, rows)


def build_kpi_cards(stats: Dict[str, Any], today_stats: Dict[str, Any], yesterday_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """۸ کارت KPI اصلی با اسپارکلاین و دلتا."""
    users_online = get_users_online_count()
    spark_rev = _revenue_sparkline(7)
    spark_orders = _orders_sparkline(7)
    spark_signups = _signups_sparkline(7)
    spark_lic = _licenses_sparkline(7)

    def _delta(current, previous):
        return _pct_change(int(current or 0), int(previous or 0))

    return [
        {
            'key': 'revenue_total',
            'label': 'کل درآمد',
            'sublabel': 'تومان',
            'value': stats['revenue_total'],
            'format': 'money',
            'delta': stats.get('revenue_month_change'),
            'delta_label': 'ماه جاری',
            'sparkline': spark_rev,
            'icon': 'fa-sack-dollar',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'revenue_today',
            'label': 'درآمد امروز',
            'sublabel': 'تومان',
            'value': today_stats['revenue_today'],
            'format': 'money',
            'delta': _delta(today_stats['revenue_today'], yesterday_stats['revenue_yesterday']),
            'delta_label': 'نسبت دیروز',
            'sparkline': spark_rev,
            'icon': 'fa-coins',
            'accent': 'violet',
            'status': 'ok' if today_stats['revenue_today'] else 'warn',
        },
        {
            'key': 'users_active',
            'label': 'کاربران فعال',
            'sublabel': f"+{stats['users_new_month']} این ماه",
            'value': stats['users_active'],
            'format': 'count',
            'delta': _delta(today_stats['signups_today'], yesterday_stats['signups_yesterday']),
            'delta_label': 'ثبت‌نام امروز',
            'sparkline': spark_signups,
            'icon': 'fa-users',
            'accent': 'blue',
            'status': 'ok',
        },
        {
            'key': 'licenses_active',
            'label': 'لایسنس فعال',
            'sublabel': f"{stats['licenses_expiring_soon']} در شرف انقضا",
            'value': stats['licenses_active'],
            'format': 'count',
            'delta': None,
            'delta_label': f"{stats['activations_total']} دستگاه",
            'sparkline': spark_lic,
            'icon': 'fa-key',
            'accent': 'amber',
            'status': 'warn' if stats['licenses_expiring_soon'] > 3 else 'ok',
        },
        {
            'key': 'orders_today',
            'label': 'سفارش امروز',
            'sublabel': 'پرداخت‌شده',
            'value': today_stats['orders_paid_today'],
            'format': 'count',
            'delta': _delta(today_stats['orders_paid_today'], yesterday_stats['orders_paid_yesterday']),
            'delta_label': 'نسبت دیروز',
            'sparkline': spark_orders,
            'icon': 'fa-shopping-cart',
            'accent': 'cyan',
            'status': 'ok',
        },
        {
            'key': 'conversion_rate',
            'label': 'نرخ تبدیل',
            'sublabel': 'کاربر به خرید',
            'value': stats['conversion_rate'],
            'format': 'percent',
            'delta': None,
            'delta_label': f"{stats['orders_paid']} سفارش",
            'sparkline': spark_orders,
            'icon': 'fa-chart-line',
            'accent': 'indigo',
            'status': 'ok' if stats['conversion_rate'] >= 5 else 'warn',
        },
        {
            'key': 'revenue_month',
            'label': 'درآمد ماه',
            'sublabel': '۳۰ روز اخیر',
            'value': stats['revenue_month'],
            'format': 'money',
            'delta': stats.get('revenue_month_change'),
            'delta_label': 'نسبت ماه قبل',
            'sparkline': spark_rev,
            'icon': 'fa-calendar-days',
            'accent': 'rose',
            'status': 'ok',
        },
        {
            'key': 'users_online',
            'label': 'کاربران آنلاین',
            'sublabel': '۱۵ دقیقه اخیر',
            'value': users_online,
            'format': 'count',
            'delta': None,
            'delta_label': f"{stats['users_total']} کل",
            'sparkline': spark_signups,
            'icon': 'fa-signal',
            'accent': 'emerald',
            'status': 'ok' if users_online else 'warn',
        },
    ]


def build_alerts_center(stats: Dict[str, Any], sms_balance: Dict[str, Any]) -> List[Dict[str, Any]]:
    """هشدارهای مدیریتی با اولویت."""
    alerts: List[Dict[str, Any]] = []
    catalog = [
        ('orders_failed', 'پرداخت ناموفق', 'fa-circle-xmark', 'rose', '#ecc-sales', 'failed'),
        ('licenses_expiring_soon', 'لایسنس در حال انقضا', 'fa-hourglass-half', 'amber', '#ecc-licensing', 'expiring'),
        ('sms_low', 'موجودی SMS کم', 'fa-comment-sms', 'amber', '#ecc-operations', 'sms'),
        ('unread_tickets', 'تیکت بحرانی', 'fa-headset', 'rose', '#ecc-support', 'tickets'),
        ('pending_withdrawals', 'درخواست برداشت', 'fa-wallet', 'violet', '#ecc-support', 'withdrawals'),
        ('pending_card_transfers', 'کارت‌به‌کارت معلق', 'fa-money-check', 'cyan', '#ecc-sales', 'card'),
        ('orders_pending', 'سفارش پرداخت‌نشده', 'fa-clock', 'blue', '#ecc-sales', 'pending'),
        ('users_without_license', 'بدون لایسنس فعال', 'fa-user-slash', 'indigo', '#ecc-users', 'no_license'),
    ]
    failed_orders = Order.objects.filter(status='failed').count()
    extra_counts = {'orders_failed': failed_orders, 'sms_low': 1 if sms_balance.get('is_low') and sms_balance.get('ok') else 0}

    for key, title, icon, accent, anchor, slug in catalog:
        count = int(extra_counts.get(key, stats.get(key) or 0))
        if count <= 0:
            continue
        severity = 'critical' if key in ('unread_tickets', 'sms_low', 'orders_failed') and count > 0 else 'warning'
        if key == 'sms_low':
            count = int(sms_balance.get('credit') or 0)
            detail = f'{count:,} تومان باقی‌مانده'
        else:
            detail = f'{count} مورد نیاز به اقدام'
        alerts.append({
            'key': key,
            'title': title,
            'count': count,
            'detail': detail,
            'icon': icon,
            'accent': accent,
            'anchor': anchor,
            'severity': severity,
            'slug': slug,
        })

    alerts.sort(key=lambda a: (0 if a['severity'] == 'critical' else 1, -a['count']))
    return alerts


def get_crm_overview_stats() -> Dict[str, Any]:
    """آمار CRM برای بخش نمای کلی."""
    now = timezone.now()
    month_ago = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)
    properties_new_month = CRMProperty.objects.filter(created_at__gte=month_ago).count()
    deals_open = CRMDeal.objects.exclude(stage__in=('موفق', 'ناموفق', 'لغو')).count()
    return {
        'contacts_total': Customer.objects.count(),
        'properties_total': CRMProperty.objects.count(),
        'deals_total': CRMDeal.objects.count(),
        'deals_open': deals_open,
        'reminders_total': Reminder.objects.count(),
        'reminders_due': Reminder.objects.filter(is_done=False, due_at__lte=now).count(),
        'agencies_total': CRMAgency.objects.count(),
        'team_members_total': CRMAgencyMember.objects.filter(is_active=True).count(),
        'datasets_total': Dataset.objects.count(),
        'properties_new_month': properties_new_month,
        'properties_new_week': CRMProperty.objects.filter(created_at__gte=week_ago).count(),
        'crm_growth_pct': _pct_change(
            properties_new_month,
            CRMProperty.objects.filter(
                created_at__gte=month_ago - timedelta(days=30),
                created_at__lt=month_ago,
            ).count(),
        ),
    }


def get_sales_center_stats() -> Dict[str, Any]:
    """آمار مرکز فروش."""
    today = _today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    paid_qs = Order.objects.filter(status='paid')
    return {
        'revenue_today': int(paid_qs.filter(paid_at__date=today).aggregate(t=Sum('amount'))['t'] or 0),
        'revenue_week': int(paid_qs.filter(paid_at__date__gte=week_ago).aggregate(t=Sum('amount'))['t'] or 0),
        'revenue_month': int(paid_qs.filter(paid_at__date__gte=month_ago).aggregate(t=Sum('amount'))['t'] or 0),
        'orders_failed': Order.objects.filter(status='failed').count(),
        'orders_pending': Order.objects.filter(status__in=PENDING_ORDER_STATUSES).count(),
        'orders_paid_total': paid_qs.count(),
        'avg_order_value': int(paid_qs.aggregate(avg=Avg('amount'))['avg'] or 0),
    }


def get_licensing_center_stats() -> Dict[str, Any]:
    """آمار مرکز لایسنس + نرخ تمدید واقعی (سفارش با renewal_license)."""
    now = timezone.now()
    today = _today()
    week_end = today + timedelta(days=7)
    month_ago = today - timedelta(days=30)
    paid = Order.objects.filter(status='paid')
    paid_renewals = paid.filter(renewal_license__isnull=False)
    paid_purchases = paid.filter(renewal_license__isnull=True)

    buyers_unique = paid_purchases.values('user_id').distinct().count()
    renewed_users = (
        paid_purchases.filter(
            Exists(
                Order.objects.filter(
                    user_id=OuterRef('user_id'),
                    status='paid',
                    renewal_license__isnull=False,
                )
            )
        )
        .values('user_id')
        .distinct()
        .count()
    )
    renewal_orders = paid_renewals.count()
    renewal_rate_pct = round((renewed_users / buyers_unique) * 100, 1) if buyers_unique else 0.0
    renewal_revenue = int(paid_renewals.aggregate(t=Sum('amount'))['t'] or 0)
    renewals_month = paid_renewals.filter(
        Q(paid_at__date__gte=month_ago) | Q(paid_at__isnull=True, created_at__date__gte=month_ago)
    ).count()

    return {
        'active': License.objects.filter(status='active').count(),
        'expiring': License.objects.filter(
            status='active',
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=now + timedelta(days=14),
        ).count(),
        'expired': License.objects.filter(status='expired').count(),
        'issued_today': License.objects.filter(created_at__date=today).count(),
        'issued_week': License.objects.filter(created_at__date__gte=today - timedelta(days=7)).count(),
        'renewals_week': License.objects.filter(
            status='active',
            expires_at__isnull=False,
            expires_at__date__gte=today,
            expires_at__date__lte=week_end,
        ).count(),
        'activations': LicenseActivation.objects.filter(is_active=True).count(),
        'buyers_unique': buyers_unique,
        'renewed_users': renewed_users,
        'renewal_orders': renewal_orders,
        'renewal_rate_pct': renewal_rate_pct,
        'renewal_revenue': renewal_revenue,
        'renewals_month': renewals_month,
    }


def get_recent_renewal_orders(limit: int = TABLE_FETCH_LIMIT):
    """آخرین سفارش‌های تمدید پرداخت‌شده برای جدول داشبورد."""
    return (
        Order.objects.filter(status='paid', renewal_license__isnull=False)
        .select_related('user', 'product', 'plan', 'renewal_license')
        .order_by('-paid_at', '-created_at')[:limit]
    )


def get_operations_stats() -> Dict[str, Any]:
    """آمار عملیات سیستم."""
    since_24h = timezone.now() - timedelta(hours=24)
    since_7d = timezone.now() - timedelta(days=7)
    sms_24h = SmsMessageLog.objects.filter(created_at__gte=since_24h).count()
    sms_7d = SmsMessageLog.objects.filter(created_at__gte=since_7d).count()
    sms_failed_7d = SmsMessageLog.objects.filter(created_at__gte=since_7d, status='failed').count()
    return {
        'sms_sent_24h': sms_24h,
        'sms_sent_7d': sms_7d,
        'sms_failed_7d': sms_failed_7d,
        'marketing_campaigns': get_marketing_dashboard_stats().get('campaigns_total', 0),
        'datasets_total': Dataset.objects.count(),
        'webhooks_pending': 0,
    }


def get_users_analytics_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    """آمار تحلیل کاربران."""
    now = timezone.now()
    month_ago = now - timedelta(days=30)
    returning = User.objects.filter(
        is_active=True,
        last_login__gte=month_ago,
        date_joined__lt=month_ago,
    ).count()
    new_month = stats.get('users_new_month', 0)
    retention = round((returning / stats['users_active'] * 100), 1) if stats.get('users_active') else 0
    return {
        'total': stats['users_total'],
        'active': stats['users_active'],
        'new_month': new_month,
        'new_week': stats.get('users_new_week', 0),
        'without_license': stats['users_without_license'],
        'expiring_license_users': stats['licenses_expiring_soon'],
        'online': get_users_online_count(),
        'retention_30d': retention,
        'pending_payment': stats['users_pending_payment'],
    }


def get_failed_orders_recent(limit: int = TABLE_FETCH_LIMIT):
    return (
        Order.objects.filter(status='failed')
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')[:limit]
    )


def get_top_users_by_revenue(limit: int = 8):
    return (
        User.objects.annotate(
            total_spent=Sum('orders__amount', filter=Q(orders__status='paid')),
            order_count=Count('orders', filter=Q(orders__status='paid')),
        )
        .filter(total_spent__gt=0)
        .order_by('-total_spent')[:limit]
    )


def get_system_meta() -> Dict[str, Any]:
    from django.conf import settings

    return {
        'version': getattr(settings, 'ADMIN_PANEL_VERSION', '2.0'),
        'server_status': 'operational',
        'server_label': 'عملیاتی',
    }


def _user_initials(user) -> str:
    name = (user.get_full_name() or user.username or '?').strip()
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][:1] + parts[1][:1]).upper()
    return name[:2].upper()


def enrich_activity_feed(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """غنی‌سازی فید فعالیت با آواتار و لینک."""
    type_colors = {
        'order_paid': 'emerald',
        'signup': 'blue',
        'ticket': 'rose',
        'card_transfer': 'amber',
    }
    for ev in events:
        ev['accent'] = ev.get('accent') or type_colors.get(ev['type'], 'violet')
        meta = ev.get('meta') or ''
        ev['initials'] = _user_initials(type('U', (), {'get_full_name': lambda: meta, 'username': meta})())
        if len(meta) >= 2:
            ev['initials'] = meta[:2]
        ev['href'] = '#ecc-sales' if ev['type'] == 'order_paid' else (
            '#ecc-support' if ev['type'] == 'ticket' else '#ecc-users'
        )
    return events


def build_action_queue(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """صف اقدامات فوری — اولویت‌بندی شده."""
    items: List[Dict[str, Any]] = []
    queue = [
        ('pending_card_transfers', 'پرداخت کارت‌به‌کارت', 'fa-money-check', 'amber', '#ecc-sales', 'بررسی'),
        ('unread_tickets', 'تیکت خوانده‌نشده', 'fa-headset', 'rose', '#ecc-support', 'پاسخ'),
        ('orders_pending', 'سفارش پرداخت‌نشده', 'fa-clock', 'violet', '#ecc-sales', 'پیگیری'),
        ('users_pending_payment', 'کاربر با سفارش معلق', 'fa-user-clock', 'blue', '#ecc-users', 'تماس'),
        ('licenses_expiring_soon', 'لایسنس در شرف انقضا', 'fa-hourglass-half', 'cyan', '#ecc-licensing', 'تمدید'),
        ('pending_withdrawals', 'برداشت همکار فروش', 'fa-wallet', 'emerald', '#ecc-support', 'تأیید'),
        ('users_without_license', 'بدون لایسنس فعال', 'fa-user-slash', 'indigo', '#ecc-users', 'فروش'),
    ]
    for key, title, icon, accent, anchor, action in queue:
        count = int(stats.get(key) or 0)
        if count > 0:
            items.append({
                'key': key,
                'title': title,
                'count': count,
                'icon': icon,
                'accent': accent,
                'anchor': anchor,
                'action': action,
            })
    return items


def get_activity_feed(limit: int = 14) -> List[Dict[str, Any]]:
    """فید فعالیت اخیر — سفارش، ثبت‌نام، تیکت، کارت‌به‌کارت."""
    events: List[Dict[str, Any]] = []

    for order in (
        Order.objects.filter(status='paid')
        .select_related('user', 'product')
        .order_by('-paid_at')[:8]
    ):
        if not order.paid_at:
            continue
        events.append({
            'type': 'order_paid',
            'icon': 'fa-circle-check',
            'accent': 'emerald',
            'title': f'پرداخت {order.product.title if order.product_id else "سفارش"}',
            'meta': order.user.get_full_name() or order.user.username,
            'initials': _user_initials(order.user),
            'amount': int(order.amount or 0),
            'at': order.paid_at,
            'href': '#ecc-sales',
        })

    for user in User.objects.order_by('-date_joined')[:6]:
        events.append({
            'type': 'signup',
            'icon': 'fa-user-plus',
            'accent': 'blue',
            'title': 'ثبت‌نام جدید',
            'meta': user.get_full_name() or user.username or user.phone,
            'initials': _user_initials(user),
            'amount': None,
            'at': user.date_joined,
            'href': '#ecc-users',
        })

    for ticket in (
        Ticket.objects.exclude(status='closed')
        .select_related('user')
        .order_by('-created_at')[:5]
    ):
        events.append({
            'type': 'ticket',
            'icon': 'fa-headset',
            'accent': 'rose',
            'title': ticket.subject[:60],
            'meta': ticket.user.get_full_name() or ticket.user.username,
            'initials': _user_initials(ticket.user),
            'amount': None,
            'at': ticket.created_at,
            'unread': ticket.staff_has_unread,
            'href': '#ecc-support',
        })

    for ct in (
        CardTransferSubmission.objects.filter(status='pending')
        .select_related('order__user', 'order__product')
        .order_by('-created_at')[:4]
    ):
        events.append({
            'type': 'card_transfer',
            'icon': 'fa-money-check',
            'accent': 'amber',
            'title': 'کارت‌به‌کارت در انتظار',
            'meta': ct.order.user.get_full_name() or ct.order.user.username,
            'initials': _user_initials(ct.order.user),
            'amount': int(ct.order.amount or 0),
            'at': ct.created_at,
            'href': '#ecc-sales',
        })

    events.sort(key=lambda e: e['at'], reverse=True)
    return events[:limit]


def build_health_indicators(stats: Dict[str, Any], sms_balance: Dict[str, Any]) -> List[Dict[str, Any]]:
    """وضعیت سلامت زیرسیستم‌ها."""
    indicators = [
        {
            'key': 'users',
            'label': 'کاربران',
            'status': 'ok' if stats.get('users_active', 0) > 0 else 'warn',
            'detail': f"{stats.get('users_active', 0)} فعال",
        },
        {
            'key': 'licenses',
            'label': 'لایسنس',
            'status': 'warn' if stats.get('licenses_expiring_soon', 0) > 5 else 'ok',
            'detail': f"{stats.get('licenses_active', 0)} فعال",
        },
        {
            'key': 'orders',
            'label': 'سفارش',
            'status': 'warn' if stats.get('orders_pending', 0) > 10 else 'ok',
            'detail': f"{stats.get('conversion_rate', 0)}٪ تبدیل",
        },
        {
            'key': 'sms',
            'label': 'پیامک',
            'status': 'error' if sms_balance.get('error') else ('warn' if sms_balance.get('is_low') else 'ok'),
            'detail': (
                f"{int(sms_balance.get('credit') or 0):,} ت"
                if sms_balance.get('ok') else 'خطا'
            ),
        },
        {
            'key': 'support',
            'label': 'پشتیبانی',
            'status': 'warn' if stats.get('unread_tickets', 0) > 0 else 'ok',
            'detail': f"{stats.get('open_tickets', 0)} تیکت باز",
        },
    ]
    return indicators


def get_affiliate_partners(limit: int = TABLE_FETCH_LIMIT):
    """لیست مشاوران فروش با آمار کمیسیون."""
    return (
        Affiliate.objects.select_related('user', 'user__wallet')
        .annotate(
            sales_count=Count('sales'),
            sales_paid=Count('sales', filter=Q(sales__status='paid')),
            commission_total=Sum(
                'sales__commission_amount',
                filter=Q(sales__status='paid'),
            ),
            commission_pending=Sum(
                'sales__commission_amount',
                filter=Q(sales__status='pending'),
            ),
        )
        .order_by('-sales_paid', '-created_at')[:limit]
    )


def get_recent_affiliate_sales(limit: int = TABLE_FETCH_LIMIT):
    """فروش‌های اخیر همکاری در فروش."""
    return (
        AffiliateSale.objects.select_related(
            'affiliate',
            'affiliate__user',
            'order',
            'order__user',
            'order__product',
        )
        .order_by('-created_at')[:limit]
    )


def get_admin_dashboard_context(days: int = 30) -> Dict[str, Any]:
    stats = get_overview_stats()
    sms_balance = get_sms_balance_snapshot()
    order_status = get_order_status_breakdown()
    license_status = get_license_status_breakdown()
    payment_methods = get_payment_method_breakdown()
    plan_sales = get_plan_sales_breakdown()
    product_revenue = get_product_revenue()
    status_max = max((item['count'] for item in order_status), default=1) or 1
    today_stats = get_today_stats()
    yesterday_stats = get_yesterday_stats()
    marketing_stats = get_marketing_dashboard_stats()
    alerts_center = build_alerts_center(stats, sms_balance)
    alert_count = len(alerts_center)
    marketing_segments = [
        {
            'key': key,
            'title': meta.get('title', key),
            'accent': meta.get('accent', 'violet'),
            'icon': meta.get('icon', 'fa-bullhorn'),
            'size': marketing_stats.get('segment_sizes', {}).get(key, 0),
        }
        for key, meta in SEGMENT_REGISTRY.items()
    ]

    return {
        'stats': stats,
        'today_stats': today_stats,
        'yesterday_stats': yesterday_stats,
        'sms_balance': sms_balance,
        'kpi_cards': build_kpi_cards(stats, today_stats, yesterday_stats),
        'alerts_center': alerts_center,
        'alert_count': alert_count,
        'command_modules': build_command_modules(stats, alert_count=alert_count),
        'growth_snapshot': get_growth_pipeline_snapshot(),
        'crm_stats': get_crm_overview_stats(),
        'sales_stats': get_sales_center_stats(),
        'licensing_stats': get_licensing_center_stats(),
        'recent_renewals': get_recent_renewal_orders(),
        'operations_stats': get_operations_stats(),
        'users_analytics': get_users_analytics_stats(stats),
        'marketing_stats': marketing_stats,
        'marketing_segments': marketing_segments,
        'blog_stats': get_blog_dashboard_stats(),
        'academy_stats': get_academy_dashboard_stats(),
        'recovery_stats': get_recovery_flow_bridge_stats(days=days),
        'system_meta': get_system_meta(),
        'failed_orders': get_failed_orders_recent(),
        'top_users': get_top_users_by_revenue(),
        'action_queue': build_action_queue(stats),
        'activity_feed': get_activity_feed(),
        'health_indicators': build_health_indicators(stats, sms_balance),
        'charts': build_charts_payload(days),
        'order_status': order_status,
        'order_status_max': status_max,
        'license_status': license_status,
        'license_status_max': max((item['count'] for item in license_status), default=1) or 1,
        'payment_methods': payment_methods,
        'plan_sales': plan_sales,
        'product_revenue': product_revenue,
        'recent_orders': get_recent_orders(),
        'recent_users': get_recent_users(),
        'pending_orders': get_pending_orders(),
        'users_with_pending_orders': get_users_with_pending_orders(),
        'expiring_licenses': get_expiring_licenses(),
        'users_without_license_list': get_users_without_license_preview(),
        'pending_card_transfers': get_pending_card_transfers(),
        'open_tickets': get_open_tickets(),
        'pending_withdrawals': get_pending_withdrawals(),
        'affiliate_partners': get_affiliate_partners(),
        'recent_affiliate_sales': get_recent_affiliate_sales(),
        'table_preview_rows': TABLE_PREVIEW_ROWS,
        'export_catalog': get_export_catalog(days=days),
        'export_categories': {
            'orders': 'سفارش‌ها',
            'users': 'کاربران',
            'licenses': 'لایسنس‌ها',
            'finance': 'مالی',
            'support': 'پشتیبانی',
        },
        'chart_days': days,
        'products_count': Product.objects.filter(is_active=True).count(),
        'windows_app_stats': get_windows_app_stats(),
        'windows_download_logs': get_windows_download_logs(TABLE_FETCH_LIMIT),
        'windows_activations': get_windows_activations(TABLE_FETCH_LIMIT),
        'windows_first_launches': get_windows_first_launches(TABLE_FETCH_LIMIT),
        'windows_user_funnel': get_windows_user_funnel(TABLE_FETCH_LIMIT),
    }


def build_command_modules(stats: Dict[str, Any], *, alert_count: int = 0) -> List[Dict[str, Any]]:
    """میانبرهای سطح‌بالا برای مدیر — یک نگاه."""
    return [
        {
            'title': 'پایپلاین رشد',
            'desc': 'سرنخ تا خرید',
            'icon': 'fa-route',
            'accent': 'teal',
            'url_name': 'admin_panel_growth_pipeline',
            'badge': None,
        },
        {
            'title': 'جذب سرنخ',
            'desc': 'ورود فایل و کمپین',
            'icon': 'fa-user-plus',
            'accent': 'cyan',
            'url_name': 'admin_panel_lead_acquisition',
            'badge': None,
        },
        {
            'title': 'بازاریابی',
            'desc': 'سگمنت و پیامک',
            'icon': 'fa-bullhorn',
            'accent': 'violet',
            'url_name': 'admin_panel_marketing',
            'badge': None,
        },
        {
            'title': 'بازیابی',
            'desc': 'سبد معلق',
            'icon': 'fa-rotate-left',
            'accent': 'amber',
            'url_name': 'admin_panel_recovery_center',
            'badge': int(stats.get('orders_pending') or 0) or None,
        },
        {
            'title': 'تبدیل پلن',
            'desc': 'قیف فروش',
            'icon': 'fa-filter-circle-dollar',
            'accent': 'blue',
            'url_name': 'admin_panel_plan_conversion',
            'badge': None,
        },
        {
            'title': 'مقالات',
            'desc': 'محتوا',
            'icon': 'fa-newspaper',
            'accent': 'indigo',
            'url_name': 'admin_panel_blog',
            'badge': None,
        },
        {
            'title': 'آکادمی',
            'desc': 'ویدیو',
            'icon': 'fa-graduation-cap',
            'accent': 'emerald',
            'url_name': 'admin_panel_academy',
            'badge': None,
        },
        {
            'title': 'Django Admin',
            'desc': 'تنظیمات عمیق',
            'icon': 'fa-gears',
            'accent': 'slate',
            'href': '/admin/',
            'badge': alert_count or None,
        },
    ]


def get_growth_pipeline_snapshot() -> Dict[str, Any]:
    """خلاصه سبک برای کارت رشد در داشبورد اصلی."""
    try:
        from accounts.models import GrowthJourney
        from django.db.models import Count
        counts = {
            row['stage']: row['c']
            for row in GrowthJourney.objects.values('stage').annotate(c=Count('id'))
        }
        cold = int(counts.get(GrowthJourney.Stage.COLD_LEAD, 0) or 0)
        engaged = int(counts.get(GrowthJourney.Stage.ENGAGED, 0) or 0)
        registered = int(counts.get(GrowthJourney.Stage.REGISTERED, 0) or 0)
        activated = int(counts.get(GrowthJourney.Stage.ACTIVATED, 0) or 0)
        nurture = int(counts.get(GrowthJourney.Stage.NURTURE_UNPAID, 0) or 0)
        pending = int(counts.get(GrowthJourney.Stage.PENDING_CHECKOUT, 0) or 0)
        customers = int(counts.get(GrowthJourney.Stage.CUSTOMER, 0) or 0)
        total = sum(int(v or 0) for v in counts.values())
        return {
            'total': total,
            'pre_signup': cold + engaged,
            'waiting_purchase': registered + activated + nurture,
            'pending_checkout': pending,
            'customers': customers,
        }
    except Exception:
        return {
            'total': 0,
            'pre_signup': 0,
            'waiting_purchase': 0,
            'pending_checkout': 0,
            'customers': 0,
        }
