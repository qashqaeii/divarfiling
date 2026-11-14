"""مرکز فروش — KPI، نمودار و جداول با بازه مرکزی Command Center."""
from __future__ import annotations

from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.urls import reverse

from accounts.services.admin_presentation import prioritize_management_actions
from accounts.services.admin_sales_failed_orders import build_failed_order_rows

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
    get_repeat_purchase_orders_qs,
    get_revenue_series,
    get_today_stats,
    is_all_time_range,
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
from workspace.services.jalali_input import to_persian_digits
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

SALES_PULSE_KEYS = (
    ('revenue_range', 'range'),
    ('paid_orders_range', 'range'),
    ('aov', 'range'),
    ('orders_pending', 'snapshot'),
)

SALES_HERO_CHART_LEGEND = [
    {'key': 'revenue', 'label': 'درآمد'},
    {'key': 'orders', 'label': 'سفارش موفق'},
]

SALES_ORDERS_CHART_LEGEND = [
    {'key': 'orders', 'label': 'سفارش موفق · روزانه'},
]

SALES_RANGE_KPI_SEQUENCE = (
    'revenue_range',
    'paid_orders_range',
    'aov',
    'repeat_revenue_range',
    'repeat_orders_range',
    'unique_buyers',
    'conversion_rate',
    'revenue_delta',
)

SALES_SNAPSHOT_KPI_SEQUENCE = (
    'revenue_today',
    'orders_pending',
    'pending_revenue',
    'orders_failed_today',
    'fulfillment_incomplete',
    'card_transfers_pending',
)


def _previous_period_foot_label(days: int) -> str:
    """برچسب ردیف مقایسه در کارت KPI — بازهٔ هم‌مدت قبل از انتخاب فعلی."""
    if is_all_time_range(days):
        return 'بازهٔ هم‌طول قبلی'
    if days == 1:
        return 'بازهٔ مشابه · دیروز'
    if days == 30:
        return 'بازهٔ مشابه یک‌ماهه'
    if days == 90:
        return 'بازهٔ مشابه سه‌ماهه'
    return f'بازهٔ مشابه {to_persian_digits(days)} روزه'


def _delta_vs_previous_label(days: int) -> str:
    if is_all_time_range(days):
        return 'نسبت به بازهٔ قبلی'
    return f'نسبت به {_previous_period_foot_label(days)}'


def _foot_hint_in_range(phrase: str, days: int) -> str:
    """جملهٔ توضیحی کوتاه برای KPI بازه — فارسی روان."""
    label = _range_label_fa(days)
    if days == 1:
        return f'{phrase} امروز.'
    if is_all_time_range(days):
        return f'{phrase} در کل بازهٔ ثبت‌شده.'
    return f'{phrase} در {label}.'


def _hint_repeat_revenue_share(repeat_share: float, revenue_range: int, days: int) -> str:
    if not revenue_range:
        return 'هنوز درآمدی از تمدید یا خرید مجدد در این بازه ثبت نشده است.'
    share_fa = to_persian_digits(f'{repeat_share:.1f}')
    tail = _range_label_fa(days)
    if days == 1:
        return f'امروز {share_fa}٪ از درآمد مربوط به تمدید یا خرید مجدد مشتریان بوده است.'
    if is_all_time_range(days):
        return f'در کل بازه، {share_fa}٪ از درآمد مربوط به تمدید یا خرید مجدد مشتریان است.'
    return f'در {tail}، {share_fa}٪ از درآمد مربوط به تمدید یا خرید مجدد مشتریان بوده است.'


def _hint_repeat_orders(days: int) -> str:
    label = _range_label_fa(days)
    if days == 1:
        return 'تعداد تمدید و خرید مجدد امروز؛ اولین خرید موفق هر مشتری در این عدد نیست.'
    if is_all_time_range(days):
        return 'تعداد تمدید و خرید مجدد در کل بازه؛ اولین خرید موفق هر مشتری در این عدد نیست.'
    return f'تعداد تمدید و خرید مجدد در {label}؛ اولین خرید موفق هر مشتری در این عدد نیست.'


def _hint_conversion(cohort_converted: int, new_users: int) -> str:
    if not new_users:
        return 'در این بازه کاربر تازه‌ای ثبت‌نام نکرده است.'
    return (
        f'از {to_persian_digits(new_users)} عضو جدید، '
        f'{to_persian_digits(cohort_converted)} نفر در همان بازه خرید کرده‌اند.'
    )


def _hint_revenue_growth(revenue_delta: float | None, prev_revenue: int) -> str:
    if revenue_delta is None and not prev_revenue:
        return 'برای محاسبهٔ رشد، دادهٔ بازهٔ قبلی در دسترس نیست.'
    return 'درصد تغییر درآمد نسبت به بازهٔ هم‌مدتِ قبل از این.'


def _order_kpi_cards(cards: List[Dict[str, Any]], sequence: tuple[str, ...]) -> List[Dict[str, Any]]:
    by_key = {card['key']: card for card in cards}
    return [by_key[key] for key in sequence if key in by_key]


def _repeat_orders_between(start, end) -> int:
    return get_repeat_purchase_orders_qs().filter(
        paid_at__date__gte=start,
        paid_at__date__lte=end,
    ).count()


def _repeat_revenue_between(start, end) -> int:
    return int(
        get_repeat_purchase_orders_qs()
        .filter(paid_at__date__gte=start, paid_at__date__lte=end)
        .aggregate(total=Sum('amount'))['total']
        or 0
    )


def _pending_orders_amount() -> int:
    return int(
        Order.objects.filter(status__in=PENDING_ORDER_STATUSES).aggregate(total=Sum('amount'))['total']
        or 0
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


def _percent_point_delta(current: float, previous: float) -> float | None:
    """تفاوت درصدی مطلق (نقطه) — مناسب نمایش کنار شاخص‌های درصدی."""
    if current is None or previous is None:
        return None
    return round(float(current) - float(previous), 1)


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
                    'tension': 0.35,
                    'yAxisID': 'y',
                },
                {
                    'label': 'سفارش پرداخت‌شده',
                    'data': orders['values'],
                    'type': 'bar',
                    'backgroundColor': 'rgba(124, 58, 237, 0.55)',
                    'borderRadius': 5,
                    'yAxisID': 'y1',
                },
            ],
            'axis': 'money',
        },
        'sales_trend': {
            'type': 'bar',
            'chartKind': 'sales_orders_trend',
            'labels': orders['labels'],
            'datasets': [{
                'label': 'سفارش موفق',
                'data': orders['values'],
                'backgroundColor': 'rgba(91, 79, 207, 0.28)',
                'hoverBackgroundColor': 'rgba(124, 58, 237, 0.92)',
                'borderRadius': 8,
                'borderSkipped': False,
                'maxBarThickness': 26,
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
    new_users: int,
    prev_new_users: int,
    cohort_converted: int,
    repeat_orders_range: int,
    prev_repeat_orders: int,
    repeat_revenue_range: int,
    prev_repeat_revenue: int,
) -> List[Dict[str, Any]]:
    range_label = _range_label_fa(days)
    spark_rev = _revenue_sparkline(min(days, 7))
    spark_orders = _orders_sparkline(min(days, 7))

    def delta(current, previous):
        return _pct_change(int(current or 0), int(previous or 0))

    range_kind = 'range'
    prev_period_label = _previous_period_foot_label(days)
    delta_vs_prev = _delta_vs_previous_label(days)
    repeat_share = (
        round((repeat_revenue_range / revenue_range) * 100, 1) if revenue_range else 0.0
    )
    cards = [
        {
            'key': 'revenue_range',
            'kind': range_kind,
            'label': 'درآمد بازه',
            'value': revenue_range,
            'format': 'money',
            'delta': delta(revenue_range, prev_revenue),
            'delta_label': delta_vs_prev,
            'previous_value': prev_revenue,
            'previous_foot_label': prev_period_label,
            'foot_hint': _foot_hint_in_range('جمع کل درآمد سفارش‌های پرداخت‌شده', days),
            'sparkline': spark_rev,
            'icon': 'fa-sack-dollar',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'paid_orders_range',
            'kind': range_kind,
            'label': 'سفارش موفق',
            'value': paid_orders_range,
            'format': 'count',
            'delta': delta(paid_orders_range, prev_orders),
            'delta_label': delta_vs_prev,
            'previous_value': prev_orders,
            'previous_foot_label': prev_period_label,
            'foot_hint': _foot_hint_in_range('تعداد سفارش‌هایی که پرداختشان موفق بوده', days),
            'sparkline': spark_orders,
            'icon': 'fa-cart-shopping',
            'accent': 'violet',
            'status': 'ok',
        },
        {
            'key': 'aov',
            'kind': range_kind,
            'label': 'میانگین سفارش',
            'value': aov,
            'format': 'money',
            'delta': delta(aov, prev_aov),
            'delta_label': delta_vs_prev,
            'previous_value': prev_aov,
            'previous_foot_label': prev_period_label,
            'foot_hint': _foot_hint_in_range('میانگین مبلغ هر سفارش پرداخت‌شده', days),
            'sparkline': spark_rev,
            'icon': 'fa-receipt',
            'accent': 'amber',
            'status': 'ok',
        },
        {
            'key': 'repeat_revenue_range',
            'kind': range_kind,
            'label': 'درآمد خرید مجدد',
            'value': repeat_revenue_range,
            'format': 'money',
            'delta': delta(repeat_revenue_range, prev_repeat_revenue),
            'delta_label': delta_vs_prev,
            'previous_value': prev_repeat_revenue,
            'previous_foot_label': prev_period_label,
            'foot_hint': _hint_repeat_revenue_share(repeat_share, revenue_range, days),
            'sparkline': spark_rev,
            'icon': 'fa-rotate',
            'accent': 'indigo',
            'status': 'ok',
        },
        {
            'key': 'repeat_orders_range',
            'kind': range_kind,
            'label': 'تمدید و خرید مجدد',
            'value': repeat_orders_range,
            'format': 'count',
            'delta': delta(repeat_orders_range, prev_repeat_orders),
            'delta_label': delta_vs_prev,
            'previous_value': prev_repeat_orders,
            'previous_foot_label': prev_period_label,
            'foot_hint': _hint_repeat_orders(days),
            'sparkline': spark_orders,
            'icon': 'fa-arrows-rotate',
            'accent': 'rose',
            'status': 'ok',
        },
        {
            'key': 'conversion_rate',
            'kind': range_kind,
            'label': 'خرید پس از عضویت',
            'value': conversion_rate if new_users else None,
            'format': 'percent',
            'delta': _percent_point_delta(conversion_rate, prev_conversion) if new_users else None,
            'delta_format': 'points',
            'delta_label': f'تفاوت نسبت به {prev_period_label}',
            'previous_value': prev_conversion if prev_new_users else None,
            'previous_foot_label': prev_period_label,
            'foot_hint': _hint_conversion(cohort_converted, new_users),
            'pending': not new_users,
            'sparkline': spark_orders,
            'icon': 'fa-user-check',
            'accent': 'cyan',
            'status': 'ok',
        },
        {
            'key': 'unique_buyers',
            'kind': range_kind,
            'label': 'مشتری خریدار',
            'value': unique_buyers,
            'format': 'count',
            'delta': delta(unique_buyers, prev_unique_buyers),
            'delta_label': delta_vs_prev,
            'previous_value': prev_unique_buyers,
            'previous_foot_label': prev_period_label,
            'foot_hint': _foot_hint_in_range('تعداد مشتریانی که حداقل یک خرید موفق داشته‌اند', days),
            'sparkline': spark_orders,
            'icon': 'fa-users',
            'accent': 'blue',
            'status': 'ok',
        },
        {
            'key': 'revenue_delta',
            'kind': range_kind,
            'label': 'رشد درآمد',
            'value': revenue_delta,
            'format': 'percent',
            'delta': None,
            'previous_value': prev_revenue if prev_revenue else None,
            'previous_format': 'money',
            'previous_foot_label': prev_period_label,
            'foot_hint': _hint_revenue_growth(revenue_delta, prev_revenue),
            'pending': revenue_delta is None and not prev_revenue,
            'sparkline': spark_rev,
            'icon': 'fa-chart-line',
            'accent': 'indigo',
            'status': 'ok' if revenue_delta is None or revenue_delta >= 0 else 'warn',
        },
    ]
    return _order_kpi_cards(cards, SALES_RANGE_KPI_SEQUENCE)


def _build_snapshot_kpi_cards(
    snapshot: Dict[str, int],
    today_stats: Dict[str, Any],
    pending_revenue: int,
) -> List[Dict[str, Any]]:
    pending_count = int(snapshot.get('orders_pending') or 0)
    cards = [
        {
            'key': 'revenue_today',
            'kind': 'snapshot',
            'label': 'درآمد امروز',
            'foot_hint': (
                f"بر اساس {to_persian_digits(int(today_stats.get('orders_paid_today') or 0))} "
                f"سفارش پرداخت‌شدهٔ امروز."
            ),
            'value': int(today_stats.get('revenue_today') or 0),
            'format': 'money',
            'icon': 'fa-sun',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'orders_pending',
            'kind': 'snapshot',
            'label': 'پرداخت‌نشده',
            'foot_hint': 'سفارش‌هایی که هنوز به وضعیت پرداخت‌شده نرسیده‌اند.',
            'value': pending_count,
            'format': 'count',
            'icon': 'fa-clock',
            'accent': 'violet',
            'status': 'warn' if pending_count else 'ok',
        },
        {
            'key': 'pending_revenue',
            'kind': 'snapshot',
            'label': 'ارزش معلق',
            'foot_hint': 'مجموع مبلغ سفارش‌هایی که هنوز پرداخت نشده‌اند.',
            'value': pending_revenue,
            'format': 'money',
            'icon': 'fa-wallet',
            'accent': 'amber',
            'status': 'warn' if pending_revenue else 'ok',
        },
        {
            'key': 'orders_failed_today',
            'kind': 'snapshot',
            'label': 'ناموفق امروز',
            'foot_hint': 'تعداد پرداخت‌های رد‌شده یا لغو‌شده در روز جاری.',
            'value': int(snapshot.get('orders_failed_today') or 0),
            'format': 'count',
            'icon': 'fa-circle-xmark',
            'accent': 'rose',
            'status': 'warn' if snapshot.get('orders_failed_today') else 'ok',
        },
        {
            'key': 'fulfillment_incomplete',
            'kind': 'snapshot',
            'label': 'صدور ناقص',
            'foot_hint': 'پرداخت انجام شده اما صدور یا تمدید لایسنس هنوز کامل نشده است.',
            'value': int(snapshot.get('fulfillment_incomplete') or 0),
            'format': 'count',
            'icon': 'fa-key',
            'accent': 'rose',
            'status': 'warn' if snapshot.get('fulfillment_incomplete') else 'ok',
        },
        {
            'key': 'card_transfers_pending',
            'kind': 'snapshot',
            'label': 'کارت‌به‌کارت',
            'foot_hint': 'واریزهای کارت‌به‌کارت که منتظر تأیید در پنل هستند.',
            'value': int(snapshot.get('pending_card_transfers') or 0),
            'format': 'count',
            'icon': 'fa-money-check',
            'accent': 'cyan',
            'status': 'warn' if snapshot.get('pending_card_transfers') else 'ok',
        },
    ]
    return _order_kpi_cards(cards, SALES_SNAPSHOT_KPI_SEQUENCE)


def build_sales_center_pulse(
    range_kpi_cards: List[Dict[str, Any]],
    snapshot_kpi_cards: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    range_by = {card['key']: card for card in range_kpi_cards}
    snapshot_by = {card['key']: card for card in snapshot_kpi_cards}
    href_map = {
        'revenue_range': '#sales-kpi',
        'paid_orders_range': '#sales-kpi',
        'aov': '#sales-kpi',
        'orders_pending': '#sales-table-pending',
    }
    pulse: List[Dict[str, Any]] = []
    for key, kind in SALES_PULSE_KEYS:
        card = range_by.get(key) if kind == 'range' else snapshot_by.get(key)
        if not card:
            continue
        chip: Dict[str, Any] = {
            'key': key,
            'label': card['label'],
            'value': card['value'],
            'format': card['format'],
            'icon': card['icon'],
            'accent': card['accent'],
            'href': href_map.get(key),
            'pulse_kind': kind,
        }
        if kind == 'range':
            chip['delta'] = card.get('delta')
            chip['delta_label'] = card.get('delta_label') or 'نسبت به بازهٔ مشابه'
            chip['previous_value'] = card.get('previous_value')
        else:
            chip['hint'] = card.get('sublabel') or 'وضعیت فعلی'
        pulse.append(chip)
    return pulse


def _sales_hero_chart_summary(
    *,
    revenue_range: int,
    paid_orders_range: int,
    aov: int,
) -> List[Dict[str, Any]]:
    return [
        {
            'key': 'revenue_sum',
            'label': 'درآمد بازه',
            'value': revenue_range,
            'format': 'money',
            'icon': 'fa-sack-dollar',
        },
        {
            'key': 'orders_sum',
            'label': 'سفارش موفق',
            'value': paid_orders_range,
            'format': 'count',
            'icon': 'fa-cart-shopping',
        },
        {
            'key': 'aov',
            'label': 'میانگین سفارش',
            'value': aov,
            'format': 'money',
            'icon': 'fa-receipt',
        },
    ]


def _sales_orders_chart_summary(
    *,
    paid_orders_range: int,
    unique_buyers: int,
    conversion_rate: float,
) -> List[Dict[str, Any]]:
    return [
        {
            'key': 'orders_sum',
            'label': 'کل سفارش',
            'value': paid_orders_range,
            'format': 'count',
            'icon': 'fa-cart-shopping',
        },
        {
            'key': 'buyers',
            'label': 'مشتری یکتا',
            'value': unique_buyers,
            'format': 'count',
            'icon': 'fa-users',
        },
        {
            'key': 'conversion',
            'label': 'خرید پس از عضویت',
            'value': conversion_rate,
            'format': 'percent',
            'icon': 'fa-arrow-trend-up',
        },
    ]


def build_sales_hero_status(
    snapshot: Dict[str, int],
    today_stats: Dict[str, Any],
    *,
    paid_orders_range: int,
    conversion_rate: float,
) -> Dict[str, Any]:
    pending = int(snapshot.get('orders_pending') or 0)
    fulfillment = int(snapshot.get('fulfillment_incomplete') or 0)
    failed_today = int(snapshot.get('orders_failed_today') or 0)
    card = int(snapshot.get('pending_card_transfers') or 0)
    queue_total = pending + fulfillment + failed_today + card

    def share(part: int) -> float:
        if not queue_total:
            return 0.0
        return round((part / queue_total) * 100, 1)

    pct_pending = share(pending)
    pct_fulfillment = share(fulfillment)
    pct_critical = share(failed_today + card)

    if fulfillment or failed_today:
        urgency = 'high'
    elif pending or card:
        urgency = 'warn'
    else:
        urgency = 'ok'

    healthy_queue = queue_total == 0
    vitality_pct = 100.0 if healthy_queue else max(0.0, round(100 - min(queue_total * 3, 40), 1))

    return {
        'queue_total': queue_total,
        'pending': pending,
        'fulfillment': fulfillment,
        'failed_today': failed_today,
        'card_pending': card,
        'critical_queue': failed_today + card,
        'pct_pending': pct_pending,
        'pct_fulfillment': pct_fulfillment,
        'pct_critical': pct_critical,
        'healthy_queue': healthy_queue,
        'vitality_pct': vitality_pct,
        'revenue_today': int(today_stats.get('revenue_today') or 0),
        'orders_paid_today': int(today_stats.get('orders_paid_today') or 0),
        'paid_orders_range': paid_orders_range,
        'conversion_rate': conversion_rate,
        'urgency': urgency,
    }


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


def _sales_export_scope_label(*, days: int, supports_days: bool) -> str:
    if not supports_days:
        return 'کل داده‌ها'
    if days == 0:
        return 'کل بازه'
    return f'بازه {to_persian_digits(days)} روزه'


def _sales_export_subtitle(key: str, meta: Dict[str, Any]) -> str:
    overrides = {
        'failed_orders': 'سفارش‌های ناموفق و لغوشده',
        'paid_orders': 'فروش موفق با جزئیات پرداخت',
        'pending_orders': 'در انتظار پرداخت یا تأیید',
        'users_pending_payment': 'کاربران با سفارش باز',
        'card_transfers_pending': 'رسیدهای منتظر تأیید',
        'affiliate_sales': 'کمیسیون و فروش مشاوران',
    }
    return overrides.get(key) or meta.get('description') or 'خروجی اکسل'


def get_sales_export_links(days: int) -> List[Dict[str, Any]]:
    from accounts.services.admin_exports import EXPORT_REGISTRY, get_export_count

    links = []
    for key in SALES_EXPORT_KEYS:
        meta = EXPORT_REGISTRY.get(key)
        if not meta:
            continue
        supports_days = bool(meta.get('supports_days'))
        d = days if supports_days else None
        links.append({
            'key': key,
            'title': meta['title'],
            'subtitle': _sales_export_subtitle(key, meta),
            'scope_label': _sales_export_scope_label(days=days, supports_days=supports_days),
            'icon': meta['icon'],
            'accent': meta['accent'],
            'count': get_export_count(key, days=d),
            'supports_days': supports_days,
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


def _build_failed_orders_context(*, focus: str | None) -> Dict[str, Any]:
    failed_today_focus = focus == 'failed_today'
    failed_orders = list(
        qs_orders_failed_today()[:TABLE_PREVIEW_ROWS]
        if failed_today_focus
        else get_failed_orders_recent(limit=TABLE_PREVIEW_ROWS)
    )
    return {
        'failed_orders': failed_orders,
        'failed_order_rows': build_failed_order_rows(failed_orders),
        'failed_orders_scope_label': 'امروز' if failed_today_focus else 'پیش‌نمایش',
    }


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
    cohort_converted = _cohort_converted_users_between(start, end)
    conversion_rate = _conversion_rate_cohort(start, end)
    prev_conversion = _conversion_rate_cohort(prev_start, prev_end)

    revenue_delta = _range_delta(days, revenue_range, prev_revenue)

    repeat_orders_range = _repeat_orders_between(start, end)
    prev_repeat_orders = _repeat_orders_between(prev_start, prev_end)
    repeat_revenue_range = _repeat_revenue_between(start, end)
    prev_repeat_revenue = _repeat_revenue_between(prev_start, prev_end)
    pending_revenue = _pending_orders_amount()

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
        new_users=new_users,
        prev_new_users=prev_new_users,
        cohort_converted=cohort_converted,
        repeat_orders_range=repeat_orders_range,
        prev_repeat_orders=prev_repeat_orders,
        repeat_revenue_range=repeat_revenue_range,
        prev_repeat_revenue=prev_repeat_revenue,
    )

    product_revenue = _product_revenue_for_range(start, end)
    plan_sales = get_plan_sales_for_date_range(start, end)
    payment_methods = _payment_methods_for_range(start, end)
    today_stats = get_today_stats()
    snapshot_counts = {
        'orders_pending': qs_orders_pending().count(),
        'orders_failed_today': qs_orders_failed_today().count(),
        'fulfillment_incomplete': count_fulfillment_incomplete(),
        'pending_card_transfers': CardTransferSubmission.objects.filter(status='pending').count(),
    }
    snapshot_kpis = _build_snapshot_kpi_cards(snapshot_counts, today_stats, pending_revenue)

    return {
        'chart_days': days,
        'range_label': range_label,
        'today_stats': today_stats,
        'center_pulse': build_sales_center_pulse(kpi_cards, snapshot_kpis),
        'range_kpi_cards': kpi_cards,
        'snapshot_kpi_cards': snapshot_kpis,
        'kpi_cards': kpi_cards + snapshot_kpis,
        'sales_hero_status': build_sales_hero_status(
            snapshot_counts,
            today_stats,
            paid_orders_range=paid_orders_range,
            conversion_rate=conversion_rate,
        ),
        'sales_hero_chart_summary': _sales_hero_chart_summary(
            revenue_range=revenue_range,
            paid_orders_range=paid_orders_range,
            aov=aov,
        ),
        'sales_orders_chart_summary': _sales_orders_chart_summary(
            paid_orders_range=paid_orders_range,
            unique_buyers=unique_buyers,
            conversion_rate=conversion_rate,
        ),
        'sales_chart_legend': SALES_HERO_CHART_LEGEND,
        'sales_orders_chart_legend': SALES_ORDERS_CHART_LEGEND,
        'charts_enabled': True,
        'charts': _build_sales_charts(days, start, end),
        'product_revenue': product_revenue,
        'plan_sales': plan_sales,
        'payment_methods': payment_methods,
        'action_items': build_sales_action_items(),
        'recent_orders': get_recent_orders(limit=TABLE_PREVIEW_ROWS),
        **_build_failed_orders_context(focus=focus),
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
        'snapshot_counts': snapshot_counts,
        **_orders_for_sales_focus(focus, limit=TABLE_FETCH_LIMIT),
    }
