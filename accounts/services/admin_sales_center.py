"""مرکز فروش — KPI، نمودار و جداول با بازه مرکزی Command Center."""
from __future__ import annotations

from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.urls import reverse

from accounts.services.admin_presentation import prioritize_management_actions

User = get_user_model()

from accounts.services.admin_dashboard import (
    CHART_COLORS,
    PAYMENT_METHOD_LABELS,
    TABLE_FETCH_LIMIT,
    TABLE_PREVIEW_ROWS,
    _date_range,
    _new_users_between,
    _orders_paid_between,
    _orders_sparkline,
    _pct_change,
    _previous_period_bounds,
    _range_delta,
    _range_label_fa,
    _revenue_between,
    _revenue_for_period,
    _revenue_sparkline,
    build_plan_sales_chart_payload,
    get_failed_orders_recent,
    get_order_count_series,
    get_pending_card_transfers,
    get_pending_orders,
    get_plan_sales_for_date_range,
    get_recent_orders,
    get_revenue_series,
    get_today_stats,
)
from accounts.services.admin_command_queues import (
    count_fulfillment_incomplete,
    fulfillment_incomplete_orders,
    get_command_queue_spec,
    qs_orders_failed_today,
    qs_orders_pending,
)
from accounts.services.admin_panel_shell import format_admin_panel_days_param
from accounts.services.pending_orders import PENDING_ORDER_STATUSES
from shop.models import CardTransferSubmission, Order
from shop.services.card_transfer_workflow import serialize_pending_card_transfers

SALES_EXPORT_KEYS = (
    'paid_orders',
    'pending_orders',
    'failed_orders',
    'users_pending_payment',
    'card_transfers_pending',
    'affiliate_sales',
)


def _unique_buyers_between(start, end) -> int:
    return (
        Order.objects.filter(
            status='paid',
            paid_at__date__gte=start,
            paid_at__date__lte=end,
        )
        .values('user_id')
        .distinct()
        .count()
    )


def _cohort_converted_users_between(start, end) -> int:
    """کاربران ثبت‌نام‌شده در بازه که در همان بازه خرید کرده‌اند."""
    return (
        User.objects.filter(
            date_joined__date__gte=start,
            date_joined__date__lte=end,
            orders__status='paid',
            orders__paid_at__date__gte=start,
            orders__paid_at__date__lte=end,
        )
        .distinct()
        .count()
    )


def _conversion_rate_cohort(start, end) -> float:
    new_users = _new_users_between(start, end)
    if not new_users:
        return 0.0
    converted = _cohort_converted_users_between(start, end)
    return round((converted / new_users) * 100, 1)


def _product_revenue_for_range(start, end, limit: int = 8) -> List[Dict[str, Any]]:
    rows = (
        Order.objects.filter(
            status='paid',
            paid_at__date__gte=start,
            paid_at__date__lte=end,
        )
        .values('product__title')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('-total')[:limit]
    )
    return [
        {
            'label': row['product__title'] or '—',
            'count': row['count'],
            'total': int(row['total'] or 0),
        }
        for row in rows
    ]


def _payment_methods_for_range(start, end) -> List[Dict[str, Any]]:
    rows = (
        Order.objects.filter(
            status='paid',
            paid_at__date__gte=start,
            paid_at__date__lte=end,
        )
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


def _build_sales_charts(days: int, start, end) -> Dict[str, Any]:
    revenue = get_revenue_series(days)
    orders = get_order_count_series(days)
    plan_sales = get_plan_sales_for_date_range(start, end)
    product_revenue = _product_revenue_for_range(start, end)
    payment_methods = _payment_methods_for_range(start, end)

    return {
        'revenue_trend': {
            'type': 'line',
            'labels': revenue['labels'],
            'datasets': [{
                'label': 'درآمد (تومان)',
                'data': revenue['values'],
                'borderColor': 'rgba(16, 185, 129, 1)',
                'backgroundColor': 'rgba(16, 185, 129, 0.12)',
                'fill': True,
                'tension': 0.35,
            }],
            'axis': 'money',
        },
        'sales_trend': {
            'type': 'bar',
            'labels': orders['labels'],
            'datasets': [{
                'label': 'سفارش پرداخت‌شده',
                'data': orders['values'],
                'backgroundColor': 'rgba(124, 58, 237, 0.75)',
                'borderRadius': 6,
            }],
            'axis': 'count',
        },
        'plan_sales': build_plan_sales_chart_payload(plan_sales) if plan_sales else None,
        'product_revenue': {
            'type': 'bar',
            'labels': [item['label'] for item in product_revenue],
            'datasets': [{
                'label': 'درآمد (تومان)',
                'data': [item['total'] for item in product_revenue],
                'backgroundColor': CHART_COLORS[:len(product_revenue)],
                'borderRadius': 6,
            }],
            'axis': 'money',
        } if product_revenue else None,
        'payment_methods': {
            'type': 'bar',
            'labels': [item['label'] for item in payment_methods],
            'datasets': [{
                'label': 'تعداد سفارش',
                'data': [item['count'] for item in payment_methods],
                'backgroundColor': 'rgba(6, 182, 212, 0.75)',
                'borderRadius': 6,
            }],
            'axis': 'count',
        } if payment_methods else None,
    }


def _build_sales_kpi_cards(
    *,
    days: int,
    revenue_range: int,
    paid_orders_range: int,
    aov: int,
    conversion_rate: float,
    unique_buyers: int,
    revenue_delta: float | None,
    prev_revenue: int,
    prev_orders: int,
    prev_aov: int,
    prev_conversion: float,
    prev_unique_buyers: int,
) -> List[Dict[str, Any]]:
    range_label = _range_label_fa(days)
    spark_rev = _revenue_sparkline(min(days, 7))
    spark_orders = _orders_sparkline(min(days, 7))

    def delta(current, previous):
        return _pct_change(int(current or 0), int(previous or 0))

    range_kind = 'range'
    return [
        {
            'key': 'revenue_range',
            'kind': range_kind,
            'label': 'درآمد بازه',
            'sublabel': f'{range_label} · تومان',
            'value': revenue_range,
            'format': 'money',
            'delta': delta(revenue_range, prev_revenue),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark_rev,
            'icon': 'fa-sack-dollar',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'paid_orders_range',
            'kind': range_kind,
            'label': 'سفارش موفق',
            'sublabel': range_label,
            'value': paid_orders_range,
            'format': 'count',
            'delta': delta(paid_orders_range, prev_orders),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark_orders,
            'icon': 'fa-cart-shopping',
            'accent': 'violet',
            'status': 'ok',
        },
        {
            'key': 'aov',
            'kind': range_kind,
            'label': 'میانگین سفارش',
            'sublabel': 'AOV · تومان',
            'value': aov,
            'format': 'money',
            'delta': delta(aov, prev_aov),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark_rev,
            'icon': 'fa-receipt',
            'accent': 'amber',
            'status': 'ok',
        },
        {
            'key': 'conversion_rate',
            'kind': range_kind,
            'label': 'نرخ تبدیل',
            'sublabel': 'ثبت‌نام هم‌دوره با خرید',
            'value': conversion_rate,
            'format': 'percent',
            'delta': _pct_change(conversion_rate, prev_conversion),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark_orders,
            'icon': 'fa-filter',
            'accent': 'cyan',
            'status': 'ok',
        },
        {
            'key': 'unique_buyers',
            'kind': range_kind,
            'label': 'مشتری خریدار',
            'sublabel': range_label,
            'value': unique_buyers,
            'format': 'count',
            'delta': delta(unique_buyers, prev_unique_buyers),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark_orders,
            'icon': 'fa-user-check',
            'accent': 'blue',
            'status': 'ok',
        },
        {
            'key': 'revenue_delta',
            'kind': range_kind,
            'label': 'درآمد نسبت به دوره قبل',
            'sublabel': (
                'دوره مقایسه ندارد'
                if revenue_delta is None and not prev_revenue
                else f'دوره قبل: {prev_revenue:,} تومان'
            ),
            'value': revenue_delta,
            'format': 'percent',
            'delta': None,
            'delta_label': range_label,
            'sparkline': spark_rev,
            'icon': 'fa-chart-line',
            'accent': 'indigo',
            'status': 'ok' if revenue_delta is None or revenue_delta >= 0 else 'warn',
        },
    ]


def build_sales_action_items() -> List[Dict[str, Any]]:
    """اقدامات فوری — Snapshot (وضعیت فعلی)."""
    pending = qs_orders_pending().count()
    failed_today = qs_orders_failed_today().count()
    fulfillment = count_fulfillment_incomplete()
    card_pending = CardTransferSubmission.objects.filter(status='pending').count()

    items: List[Dict[str, Any]] = []
    if pending:
        items.append({
            'key': 'orders_pending',
            'priority': 'high',
            'title': 'سفارش پرداخت‌نشده',
            'count': pending,
            'detail': f'{pending} سفارش در انتظار تسویه',
            'reason': 'پرداخت تکمیل نشده؛ پیگیری مشتری یا انقضای سفارش ممکن است.',
            'icon': 'fa-clock',
            'accent': 'violet',
            'cta': 'جدول معلق',
            'href': '#sales-table-pending',
        })
    if fulfillment:
        items.append({
            'key': 'fulfillment_incomplete',
            'priority': 'critical',
            'title': 'صدور/تمدید ناقص',
            'count': fulfillment,
            'detail': f'{fulfillment} سفارش paid بدون تکمیل',
            'reason': 'پول واریز شده ولی لایسنس یا تمدید صادر نشده؛ باید فوراً تکمیل شود.',
            'icon': 'fa-key',
            'accent': 'rose',
            'cta': 'صف fulfillment',
            'href': '#sales-queue-fulfillment',
        })
    if failed_today:
        items.append({
            'key': 'orders_failed_today',
            'priority': 'critical',
            'title': 'پرداخت ناموفق امروز',
            'count': failed_today,
            'detail': f'{failed_today} مورد امروز',
            'reason': 'خطای درگاه یا انصراف مشتری امروز؛ بررسی دلیل و تماس در صورت نیاز.',
            'icon': 'fa-circle-xmark',
            'accent': 'rose',
            'cta': 'پرداخت ناموفق',
            'href': '#sales-table-failed',
        })
    if card_pending:
        items.append({
            'key': 'pending_card_transfers',
            'priority': 'high',
            'title': 'کارت‌به‌کارت معلق',
            'count': card_pending,
            'detail': f'{card_pending} واریز در انتظار تأیید',
            'reason': 'رسید کارت‌به‌کارت بدون تأیید مانده؛ تطبیق با حساب بانکی لازم است.',
            'icon': 'fa-money-check',
            'accent': 'cyan',
            'cta': 'تأیید واریزها',
            'href': '#sales-card-transfers',
        })
    return prioritize_management_actions(items)


def get_sales_export_links(days: int) -> List[Dict[str, Any]]:
    from accounts.services.admin_exports import EXPORT_REGISTRY, get_export_count

    links = []
    for key in SALES_EXPORT_KEYS:
        meta = EXPORT_REGISTRY.get(key)
        if not meta:
            continue
        d = days if meta.get('supports_days') else None
        links.append({
            'key': key,
            'title': meta['title'],
            'icon': meta['icon'],
            'accent': meta['accent'],
            'count': get_export_count(key, days=d),
            'supports_days': meta.get('supports_days', False),
            'url': reverse('admin_panel_export', args=[key])
            + f'?format=xlsx&days={format_admin_panel_days_param(days)}',
        })
    return links


def _orders_for_sales_focus(focus: str | None, *, limit: int) -> Dict[str, Any]:
    if not focus:
        return {}
    spec = get_command_queue_spec(focus)
    if not spec:
        return {}
    rows = list(spec['queue']()[:limit])
    return {'focus': focus, 'focus_title': spec['title'], 'focus_rows': rows}


def get_sales_center_context(*, days: int = 30, compare: bool = False, focus: str | None = None) -> Dict[str, Any]:
    """Context مرکز فروش — فقط queryهای مرتبط با این صفحه."""
    del compare  # delta همیشه نسبت دوره هم‌اندازه محاسبه می‌شود

    start, end = _date_range(days)
    prev_start, prev_end = _previous_period_bounds(days)
    range_label = _range_label_fa(days)

    revenue_range = _revenue_for_period(days)
    prev_revenue = _revenue_between(prev_start, prev_end)
    paid_orders_range = _orders_paid_between(start, end)
    prev_orders = _orders_paid_between(prev_start, prev_end)

    unique_buyers = _unique_buyers_between(start, end)
    prev_unique_buyers = _unique_buyers_between(prev_start, prev_end)

    aov = int(revenue_range / paid_orders_range) if paid_orders_range else 0
    prev_aov = int(prev_revenue / prev_orders) if prev_orders else 0

    new_users = _new_users_between(start, end)
    prev_new_users = _new_users_between(prev_start, prev_end)
    conversion_rate = _conversion_rate_cohort(start, end)
    prev_conversion = _conversion_rate_cohort(prev_start, prev_end)

    revenue_delta = _range_delta(days, revenue_range, prev_revenue)

    kpi_cards = _build_sales_kpi_cards(
        days=days,
        revenue_range=revenue_range,
        paid_orders_range=paid_orders_range,
        aov=aov,
        conversion_rate=conversion_rate,
        unique_buyers=unique_buyers,
        revenue_delta=revenue_delta,
        prev_revenue=prev_revenue,
        prev_orders=prev_orders,
        prev_aov=prev_aov,
        prev_conversion=prev_conversion,
        prev_unique_buyers=prev_unique_buyers,
    )

    product_revenue = _product_revenue_for_range(start, end)
    plan_sales = get_plan_sales_for_date_range(start, end)
    payment_methods = _payment_methods_for_range(start, end)

    return {
        'chart_days': days,
        'range_label': range_label,
        'today_stats': get_today_stats(),
        'kpi_cards': kpi_cards,
        'charts': _build_sales_charts(days, start, end),
        'product_revenue': product_revenue,
        'plan_sales': plan_sales,
        'payment_methods': payment_methods,
        'action_items': build_sales_action_items(),
        'recent_orders': get_recent_orders(limit=TABLE_PREVIEW_ROWS),
        'failed_orders': (
            list(qs_orders_failed_today()[:TABLE_PREVIEW_ROWS])
            if focus == 'failed_today'
            else get_failed_orders_recent(limit=TABLE_PREVIEW_ROWS)
        ),
        'pending_orders': (
            list(qs_orders_pending()[:TABLE_PREVIEW_ROWS])
            if focus == 'pending'
            else get_pending_orders(limit=TABLE_PREVIEW_ROWS)
        ),
        'fulfillment_incomplete_orders': fulfillment_incomplete_orders(limit=TABLE_FETCH_LIMIT),
        'fulfillment_incomplete_count': count_fulfillment_incomplete(),
        'pending_card_transfers': get_pending_card_transfers(limit=TABLE_PREVIEW_ROWS),
        'card_transfer_rows': serialize_pending_card_transfers(limit=TABLE_PREVIEW_ROWS),
        'card_transfer_pending_count': CardTransferSubmission.objects.filter(status='pending').count(),
        'export_links': get_sales_export_links(days),
        'recovery_center_url': (
            reverse('admin_panel_recovery_center') + f'?days={format_admin_panel_days_param(days)}'
        ),
        'table_fetch_limit': TABLE_FETCH_LIMIT,
        'table_preview_rows': TABLE_PREVIEW_ROWS,
        'snapshot_counts': {
            'orders_pending': qs_orders_pending().count(),
            'orders_failed_today': qs_orders_failed_today().count(),
            'fulfillment_incomplete': count_fulfillment_incomplete(),
            'pending_card_transfers': CardTransferSubmission.objects.filter(status='pending').count(),
        },
        **_orders_for_sales_focus(focus, limit=TABLE_FETCH_LIMIT),
    }
