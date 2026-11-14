"""مرکز لایسنس — KPI، تمدید و جداول با بازه مرکزی Command Center."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.db.models.functions import TruncDate
from django.urls import reverse

from accounts.services.admin_presentation import prioritize_management_actions
from django.utils import timezone

from accounts.services.admin_dashboard import (
    TABLE_FETCH_LIMIT,
    TABLE_PREVIEW_ROWS,
    _chart_day_label,
    _date_range,
    _fill_daily_series,
    _licenses_sparkline,
    _pct_change,
    _previous_period_bounds,
    _range_label_fa,
    get_expiring_licenses,
    get_formal_renewal_orders_qs,
    get_recent_renewal_orders,
    get_repeat_purchase_orders_qs,
    get_users_without_license_preview,
)
from licenses.models import License, LicenseActivation
from licenses.services.renewal_orders import order_is_renewal_commerce

User = get_user_model()

LICENSES_PULSE_KEYS = (
    ('licenses_new_period', 'range'),
    ('renewals_period', 'range'),
    ('licenses_active', 'snapshot'),
    ('licenses_expiring_7d', 'snapshot'),
)

LICENSE_EXPORT_KEYS = (
    'active_licenses',
    'expiring_licenses',
    'expired_licenses',
)


def _orders_in_range_qs(start, end):
    return get_repeat_purchase_orders_qs().filter(
        paid_at__date__gte=start,
        paid_at__date__lte=end,
    )


def _licenses_new_between(start, end) -> int:
    return License.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _renewals_between(start, end) -> int:
    return _orders_in_range_qs(start, end).count()


def _renewal_revenue_between(start, end) -> int:
    return int(_orders_in_range_qs(start, end).aggregate(t=Sum('amount'))['t'] or 0)


def _formal_renewals_between(start, end) -> int:
    return get_formal_renewal_orders_qs().filter(
        paid_at__date__gte=start, paid_at__date__lte=end,
    ).count()


def _renewal_rate_period(start, end) -> float:
    renewals = _renewals_between(start, end)
    new_licenses = _licenses_new_between(start, end)
    total = renewals + new_licenses
    if not total:
        return 0.0
    return round((renewals / total) * 100, 1)


def _users_without_license_count() -> int:
    now = timezone.now()
    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return (
        User.objects.filter(is_active=True)
        .annotate(has_active_license=Exists(active_license_q))
        .filter(has_active_license=False)
        .count()
    )


def _snapshot_counts() -> Dict[str, int]:
    now = timezone.now()
    today = timezone.localdate()
    week_end = today + timedelta(days=7)
    return {
        'licenses_active': License.objects.filter(status='active').count(),
        'licenses_expiring_7d': License.objects.filter(
            status='active',
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__date__lte=week_end,
        ).count(),
        'licenses_expiring_14d': License.objects.filter(
            status='active',
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=now + timedelta(days=14),
        ).count(),
        'licenses_expired': License.objects.filter(status='expired').count(),
        'active_devices': LicenseActivation.objects.filter(is_active=True).count(),
    }


def get_recent_expired_licenses(limit: int = TABLE_PREVIEW_ROWS):
    return (
        License.objects.filter(status='expired')
        .select_related('order__user', 'plan')
        .order_by('-expires_at', '-created_at')[:limit]
    )


def _license_issued_series(days: int) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        License.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return {'labels': labels, 'values': values}


def _renewals_series(days: int) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        get_repeat_purchase_orders_qs()
        .filter(paid_at__date__gte=start, paid_at__date__lte=end)
        .annotate(day=TruncDate('paid_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return {'labels': labels, 'values': values}


def _renewal_revenue_series(days: int) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        get_repeat_purchase_orders_qs()
        .filter(paid_at__date__gte=start, paid_at__date__lte=end)
        .annotate(day=TruncDate('paid_at'))
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, value_key='total', money=True, days=days)
    return {'labels': labels, 'values': values}


def _licenses_hero_chart_summary(days: int, renewal_revenue_range: int) -> List[Dict[str, Any]]:
    issued = _license_issued_series(days)
    renewals = _renewals_series(days)
    issue_vals = issued.get('values') or []
    renew_vals = renewals.get('values') or []
    return [
        {
            'key': 'issued_sum',
            'label': 'صدور در بازه',
            'value': sum(issue_vals),
            'format': 'count',
            'icon': 'fa-key',
        },
        {
            'key': 'renew_sum',
            'label': 'تمدید در بازه',
            'value': sum(renew_vals),
            'format': 'count',
            'icon': 'fa-rotate',
        },
        {
            'key': 'renewal_revenue',
            'label': 'درآمد تمدید',
            'value': renewal_revenue_range,
            'format': 'money',
            'icon': 'fa-sack-dollar',
        },
    ]


LICENSES_HERO_CHART_LEGEND = [
    {'key': 'issued', 'label': 'لایسنس جدید'},
    {'key': 'renewals', 'label': 'تمدید / خرید مجدد'},
]

LICENSES_REVENUE_CHART_LEGEND = [
    {'key': 'revenue', 'label': 'درآمد روزانه · تومان'},
]


def _licenses_revenue_chart_summary(
    *,
    renewal_revenue: int,
    renewals: int,
    days: int,
) -> List[Dict[str, Any]]:
    rev_series = _renewal_revenue_series(days)
    values = [int(v or 0) for v in (rev_series.get('values') or [])]
    peak = max(values) if values else 0
    avg_per_renewal = int(renewal_revenue / renewals) if renewals else 0
    return [
        {
            'key': 'revenue_sum',
            'label': 'جمع بازه',
            'value': renewal_revenue,
            'format': 'money',
            'icon': 'fa-sack-dollar',
        },
        {
            'key': 'revenue_peak',
            'label': 'بیشترین روز',
            'value': peak,
            'format': 'money',
            'icon': 'fa-arrow-trend-up',
        },
        {
            'key': 'revenue_avg',
            'label': 'میانگین هر تمدید',
            'value': avg_per_renewal,
            'format': 'money',
            'icon': 'fa-divide',
        },
    ]


def _build_charts(days: int) -> Dict[str, Any]:
    issued = _license_issued_series(days)
    renewals = _renewals_series(days)
    rev = _renewal_revenue_series(days)
    return {
        'licenses_activity': {
            'type': 'combo',
            'labels': issued['labels'],
            'datasets': [
                {
                    'label': 'لایسنس جدید',
                    'data': issued['values'],
                    'type': 'bar',
                    'backgroundColor': 'rgba(124, 58, 237, 0.75)',
                    'borderRadius': 6,
                    'yAxisID': 'y1',
                },
                {
                    'label': 'تمدید / خرید مجدد',
                    'data': renewals['values'],
                    'type': 'line',
                    'borderColor': 'rgba(16, 185, 129, 1)',
                    'backgroundColor': 'rgba(16, 185, 129, 0.12)',
                    'fill': True,
                    'tension': 0.35,
                    'yAxisID': 'y',
                },
            ],
            'axis': 'count',
        },
        'renewal_revenue_trend': {
            'type': 'line',
            'labels': rev['labels'],
            'datasets': [{
                'label': 'درآمد تمدید (تومان)',
                'data': rev['values'],
                'borderColor': 'rgba(245, 158, 11, 1)',
                'backgroundColor': 'rgba(245, 158, 11, 0.12)',
                'fill': True,
                'tension': 0.35,
            }],
            'axis': 'money',
        },
    }


def _build_range_kpi_cards(
    *,
    days: int,
    licenses_new: int,
    prev_licenses_new: int,
    renewals: int,
    prev_renewals: int,
    renewal_revenue: int,
    prev_renewal_revenue: int,
    renewal_rate: float,
    prev_renewal_rate: float,
    formal_renewals: int,
    new_key_repurchase: int,
) -> List[Dict[str, Any]]:
    range_label = _range_label_fa(days)
    spark = _licenses_sparkline(min(days, 7))

    def delta(current, previous):
        if isinstance(current, float) or isinstance(previous, float):
            cur = float(current or 0)
            prev = float(previous or 0)
        else:
            cur = int(current or 0)
            prev = int(previous or 0)
        change = _pct_change(cur, prev)
        if change is None and prev == 0 and cur > 0:
            return 100.0
        if change is None and prev == 0 and cur == 0:
            return 0.0
        return change

    return [
        {
            'key': 'licenses_new_period',
            'kind': 'range',
            'label': 'لایسنس جدید',
            'sublabel': range_label,
            'value': licenses_new,
            'previous_value': prev_licenses_new,
            'format': 'count',
            'delta': delta(licenses_new, prev_licenses_new),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark,
            'icon': 'fa-key',
            'accent': 'violet',
            'status': 'ok',
        },
        {
            'key': 'renewals_period',
            'kind': 'range',
            'label': 'تمدید / خرید مجدد',
            'sublabel': f'رسمی: {formal_renewals} · کلید جدید: {new_key_repurchase}',
            'value': renewals,
            'previous_value': prev_renewals,
            'format': 'count',
            'delta': delta(renewals, prev_renewals),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark,
            'icon': 'fa-rotate',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'renewal_revenue',
            'kind': 'range',
            'label': 'درآمد تمدید',
            'sublabel': f'{range_label} · تومان',
            'value': renewal_revenue,
            'previous_value': prev_renewal_revenue,
            'format': 'money',
            'delta': delta(renewal_revenue, prev_renewal_revenue),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark,
            'icon': 'fa-sack-dollar',
            'accent': 'amber',
            'status': 'ok',
        },
        {
            'key': 'renewal_rate_period',
            'kind': 'range',
            'label': 'نرخ تمدید',
            'sublabel': f'تمدید÷(جدید+تمدید) · رسمی {formal_renewals} · خرید مجدد {new_key_repurchase}',
            'value': renewal_rate,
            'previous_value': prev_renewal_rate,
            'format': 'percent',
            'delta': delta(renewal_rate, prev_renewal_rate),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark,
            'icon': 'fa-chart-pie',
            'accent': 'cyan',
            'status': 'ok' if renewal_rate >= 15 else 'warn',
            'coverage_note': (
                'خرید مجدد کلید جدید در دسته تمدید همان کلید قرار نمی‌گیرد؛ این شاخص سهم خرید مجدد را نیز شامل می‌شود.'
                if new_key_repurchase
                else ''
            ),
        },
    ]


def _build_snapshot_kpi_cards(snapshot: Dict[str, int]) -> List[Dict[str, Any]]:
    spark = _licenses_sparkline(7)
    return [
        {
            'key': 'licenses_active',
            'kind': 'snapshot',
            'label': 'لایسنس فعال',
            'sublabel': 'وضعیت فعلی',
            'value': snapshot['licenses_active'],
            'format': 'count',
            'delta': None,
            'delta_label': 'Snapshot',
            'sparkline': spark,
            'icon': 'fa-key',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'licenses_expiring_7d',
            'kind': 'snapshot',
            'label': 'در شرف انقضا',
            'sublabel': '۷ روز آینده',
            'value': snapshot['licenses_expiring_7d'],
            'format': 'count',
            'delta': None,
            'delta_label': 'وضعیت فعلی',
            'sparkline': spark,
            'icon': 'fa-hourglass-half',
            'accent': 'amber',
            'status': 'warn' if snapshot['licenses_expiring_7d'] else 'ok',
        },
        {
            'key': 'licenses_expired',
            'kind': 'snapshot',
            'label': 'منقضی',
            'sublabel': 'وضعیت فعلی',
            'value': snapshot['licenses_expired'],
            'format': 'count',
            'delta': None,
            'delta_label': 'Snapshot',
            'sparkline': spark,
            'icon': 'fa-ban',
            'accent': 'rose',
            'status': 'warn' if snapshot['licenses_expired'] else 'ok',
        },
        {
            'key': 'active_devices',
            'kind': 'snapshot',
            'label': 'دستگاه فعال',
            'sublabel': 'Activation فعال',
            'value': snapshot['active_devices'],
            'format': 'count',
            'delta': None,
            'delta_label': 'وضعیت فعلی',
            'sparkline': spark,
            'icon': 'fa-desktop',
            'accent': 'blue',
            'status': 'ok',
        },
    ]


def _order_is_formal_renewal_preview(order) -> bool:
    if getattr(order, 'renewal_license_id', None):
        return True
    prefetched = getattr(order, '_prefetched_objects_cache', None) or {}
    items = prefetched.get('renewal_items')
    if items is not None:
        return len(items) > 0
    return order_is_renewal_commerce(order)


def build_recent_renewal_preview_rows(orders) -> Dict[str, Any]:
    """ردیف‌های جدول تمدیدهای اخیر — نوع تمدید، مبلغ، زمان نسبی."""
    now = timezone.now()
    rows: List[Dict[str, Any]] = []
    formal_count = 0
    new_key_count = 0
    for order in orders:
        is_formal = _order_is_formal_renewal_preview(order)
        if is_formal:
            formal_count += 1
            kind = 'formal'
            kind_label = 'تمدید رسمی'
        else:
            new_key_count += 1
            kind = 'repurchase'
            kind_label = 'کلید جدید'
        recency_days = None
        paid_at = getattr(order, 'paid_at', None)
        if paid_at:
            paid_local = timezone.localtime(paid_at)
            recency_days = max((now.date() - paid_local.date()).days, 0)
        product = getattr(order, 'product', None)
        plan = getattr(order, 'plan', None)
        rows.append({
            'order': order,
            'user': getattr(order, 'user', None),
            'product_title': product.title if product else None,
            'plan_name': plan.name if plan else None,
            'kind': kind,
            'kind_label': kind_label,
            'amount': order.amount,
            'paid_at': paid_at,
            'recency_days': recency_days,
        })
    return {
        'rows': rows,
        'formal_count': formal_count,
        'new_key_count': new_key_count,
        'total': len(rows),
    }


def build_users_without_license_preview_rows(users) -> Dict[str, Any]:
    """ردیف‌های جدول بدون لایسنس — اولویت پیگیری و خلاصه قطاع."""
    now = timezone.now()
    rows: List[Dict[str, Any]] = []
    paid_buyers = 0
    pending_checkout = 0
    organic = 0
    for user in users:
        paid = int(getattr(user, 'paid_orders', 0) or 0)
        pending = int(getattr(user, 'pending_orders', 0) or 0)
        if paid > 0:
            tier = 'paid'
            tier_label = 'خریدار بدون دسترسی'
            paid_buyers += 1
        elif pending > 0:
            tier = 'pending'
            tier_label = 'سفارش معلق'
            pending_checkout += 1
        else:
            tier = 'signup'
            tier_label = 'بدون خرید'
            organic += 1
        member_days = None
        if user.date_joined:
            joined = timezone.localtime(user.date_joined)
            member_days = max((now.date() - joined.date()).days, 0)
        rows.append({
            'user': user,
            'paid_orders': paid,
            'pending_orders': pending,
            'tier': tier,
            'tier_label': tier_label,
            'member_days': member_days,
            'date_joined': user.date_joined,
        })
    return {
        'rows': rows,
        'paid_buyers': paid_buyers,
        'pending_checkout': pending_checkout,
        'organic': organic,
        'total': len(rows),
    }


def build_expiring_license_preview_rows(licenses) -> List[Dict[str, Any]]:
    """ردیف‌های جدول پیش‌نمایش انقضا — با مانده روز و شدت فوریت."""
    now = timezone.now()
    rows: List[Dict[str, Any]] = []
    for lic in licenses:
        days_left = None
        if lic.expires_at:
            if lic.expires_at > now:
                days_left = max((lic.expires_at.date() - now.date()).days, 0)
            else:
                days_left = 0
        if days_left is None:
            urgency = 'muted'
        elif days_left <= 7:
            urgency = 'high'
        elif days_left <= 14:
            urgency = 'warn'
        else:
            urgency = 'ok'
        user = lic.order.user if getattr(lic, 'order', None) and lic.order_id else None
        rows.append({
            'license': lic,
            'user': user,
            'plan_name': lic.plan.name if lic.plan_id and lic.plan else None,
            'days_left': days_left,
            'urgency': urgency,
        })
    return rows


def build_recent_expired_license_preview_rows(licenses) -> Dict[str, Any]:
    """ردیف‌های جدول منقضی اخیر — فاصله از انقضا و اولویت پیگیری."""
    now = timezone.now()
    today = now.date()
    rows: List[Dict[str, Any]] = []
    recent_7 = 0
    recent_30 = 0
    older = 0
    for lic in licenses:
        days_since = None
        if lic.expires_at:
            exp_local = timezone.localtime(lic.expires_at)
            days_since = max((today - exp_local.date()).days, 0)
        if days_since is None:
            lapse = 'muted'
            older += 1
        elif days_since <= 7:
            lapse = 'high'
            recent_7 += 1
        elif days_since <= 30:
            lapse = 'warn'
            recent_30 += 1
        else:
            lapse = 'ok'
            older += 1
        user = lic.order.user if getattr(lic, 'order', None) and lic.order_id else None
        rows.append({
            'license': lic,
            'user': user,
            'plan_name': lic.plan.name if lic.plan_id and lic.plan else None,
            'days_since_expiry': days_since,
            'lapse': lapse,
        })
    return {
        'rows': rows,
        'recent_7': recent_7,
        'recent_30': recent_30,
        'older': older,
        'total': len(rows),
    }


def build_licenses_hero_status(
    snapshot: Dict[str, int],
    *,
    renewal_breakdown: Dict[str, Any],
) -> Dict[str, Any]:
    """ترکیب لحظه‌ای لایسنس برای پنل کنار نمودار هیرو."""
    active = int(snapshot.get('licenses_active') or 0)
    expiring_14 = int(snapshot.get('licenses_expiring_14d') or 0)
    expiring_7 = int(snapshot.get('licenses_expiring_7d') or 0)
    expired = int(snapshot.get('licenses_expired') or 0)
    healthy = max(active - expiring_14, 0)
    total = active + expired

    def share(part: int) -> float:
        if total <= 0:
            return 0.0
        return round((part / total) * 100, 1)

    renewal_rate = renewal_breakdown.get('renewal_rate_range')
    formal = int(renewal_breakdown.get('formal_renewals_range') or 0)
    repurchase = int(renewal_breakdown.get('new_key_repurchase_range') or 0)

    urgency = 'ok'
    if expiring_7 >= 5:
        urgency = 'high'
    elif expiring_14 or expired >= 20:
        urgency = 'warn'

    return {
        'total': total,
        'active': active,
        'healthy': healthy,
        'expiring_14d': expiring_14,
        'expiring_7d': expiring_7,
        'expired': expired,
        'pct_healthy': share(healthy),
        'pct_expiring': share(expiring_14),
        'pct_expired': share(expired),
        'vitality_pct': share(active),
        'users_without_license': int(snapshot.get('users_without_license') or 0),
        'active_devices': int(snapshot.get('active_devices') or 0),
        'renewal_rate': renewal_rate,
        'formal_renewals': formal,
        'new_key_repurchase': repurchase,
        'urgency': urgency,
    }


def build_licenses_center_pulse(
    range_kpi_cards: List[Dict[str, Any]],
    snapshot_kpi_cards: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """۴ KPI برتر: رشد و تمدید بازه + فوریت عملیاتی (فعال / انقضا)."""
    range_by = {card['key']: card for card in range_kpi_cards}
    snapshot_by = {card['key']: card for card in snapshot_kpi_cards}
    href_map = {
        'licenses_new_period': '#licenses-kpi',
        'renewals_period': '#licenses-kpi',
        'licenses_active': '#licenses-kpi',
        'licenses_expiring_7d': '#licenses-table-expiring',
    }
    pulse: List[Dict[str, Any]] = []
    for key, kind in LICENSES_PULSE_KEYS:
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
            chip['delta_label'] = card.get('delta_label') or 'نسبت دوره قبل'
            chip['previous_value'] = card.get('previous_value')
            chip['pending'] = card.get('pending')
        else:
            chip['hint'] = card.get('sublabel') or 'وضعیت فعلی'
        pulse.append(chip)
    return pulse


def build_licenses_action_items(snapshot: Dict[str, int]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    expiring = snapshot.get('licenses_expiring_14d') or snapshot.get('licenses_expiring_7d', 0)
    if expiring:
        items.append({
            'key': 'licenses_expiring',
            'priority': 'high',
            'title': 'در شرف انقضا',
            'count': expiring,
            'detail': f'{expiring} لایسنس تا ۱۴ روز آینده',
            'reason': 'انقضا در ۱۴ روز آینده؛ پیگیری تمدید قبل از قطع دسترسی مشاور.',
            'icon': 'fa-hourglass-half',
            'accent': 'amber',
            'cta': 'جدول تمدید',
            'href': '#licenses-table-expiring',
        })
    if snapshot['licenses_expired']:
        items.append({
            'key': 'licenses_expired',
            'priority': 'medium',
            'title': 'لایسنس منقضی',
            'count': snapshot['licenses_expired'],
            'detail': 'نیاز به پیگیری تمدید',
            'reason': 'دسترسی میزکار قطع شده؛ تماس برای تمدید یا بازیابی اشتراک.',
            'icon': 'fa-ban',
            'accent': 'rose',
            'cta': 'لایسنس منقضی',
            'href': '#licenses-table-expired',
        })
    without = snapshot.get('users_without_license', 0)
    if without:
        items.append({
            'key': 'users_without_license',
            'priority': 'high',
            'title': 'کاربر بدون لایسنس',
            'count': without,
            'detail': 'فرصت تبدیل به مشتری',
            'reason': 'کاربر فعال بدون لایسنس؛ مناسب کمپین فروش یا پیشنهاد پلن.',
            'icon': 'fa-user-slash',
            'accent': 'indigo',
            'cta': 'مارکتینگ',
            'href': reverse('admin_panel_marketing'),
        })
    return prioritize_management_actions(items)


def get_licenses_export_links() -> List[Dict[str, Any]]:
    from accounts.services.admin_exports import EXPORT_REGISTRY, get_export_count

    links = []
    for key in LICENSE_EXPORT_KEYS:
        meta = EXPORT_REGISTRY.get(key)
        if not meta:
            continue
        links.append({
            'key': key,
            'title': meta['title'],
            'description': meta.get('description') or 'خروجی اکسل',
            'icon': meta['icon'],
            'accent': meta['accent'],
            'count': get_export_count(key),
            'url': reverse('admin_panel_export', args=[key]) + '?format=xlsx',
        })
    return links


def get_licenses_center_context(*, days: int = 30, compare: bool = False) -> Dict[str, Any]:
    del compare

    start, end = _date_range(days)
    prev_start, prev_end = _previous_period_bounds(days)
    range_label = _range_label_fa(days)
    snapshot = _snapshot_counts()
    snapshot['users_without_license'] = _users_without_license_count()

    licenses_new = _licenses_new_between(start, end)
    prev_licenses_new = _licenses_new_between(prev_start, prev_end)
    renewals = _renewals_between(start, end)
    prev_renewals = _renewals_between(prev_start, prev_end)
    renewal_revenue = _renewal_revenue_between(start, end)
    prev_renewal_revenue = _renewal_revenue_between(prev_start, prev_end)
    renewal_rate = _renewal_rate_period(start, end)
    prev_renewal_rate = _renewal_rate_period(prev_start, prev_end)
    formal_renewals = _formal_renewals_between(start, end)
    new_key_repurchase = renewals - formal_renewals

    range_kpis = _build_range_kpi_cards(
        days=days,
        licenses_new=licenses_new,
        prev_licenses_new=prev_licenses_new,
        renewals=renewals,
        prev_renewals=prev_renewals,
        renewal_revenue=renewal_revenue,
        prev_renewal_revenue=prev_renewal_revenue,
        renewal_rate=renewal_rate,
        prev_renewal_rate=prev_renewal_rate,
        formal_renewals=formal_renewals,
        new_key_repurchase=new_key_repurchase,
    )
    snapshot_kpis = _build_snapshot_kpi_cards(snapshot)

    recent_renewals = list(get_recent_renewal_orders(limit=TABLE_PREVIEW_ROWS))
    recent_renewal_preview = build_recent_renewal_preview_rows(recent_renewals)
    expiring_list = list(get_expiring_licenses(limit=TABLE_PREVIEW_ROWS))
    renewal_breakdown = {
        'formal_renewals_range': formal_renewals,
        'new_key_repurchase_range': new_key_repurchase,
        'renewal_revenue_range': renewal_revenue,
        'renewal_rate_range': renewal_rate,
    }
    without_license_list = list(get_users_without_license_preview(limit=TABLE_PREVIEW_ROWS))
    without_license_preview = build_users_without_license_preview_rows(without_license_list)
    recent_expired_list = list(get_recent_expired_licenses(limit=TABLE_PREVIEW_ROWS))
    recent_expired_preview = build_recent_expired_license_preview_rows(recent_expired_list)

    return {
        'chart_days': days,
        'range_label': range_label,
        'center_pulse': build_licenses_center_pulse(range_kpis, snapshot_kpis),
        'range_kpi_cards': range_kpis,
        'snapshot_kpi_cards': snapshot_kpis,
        'kpi_cards': range_kpis + snapshot_kpis,
        'status_distribution': {
            'active': snapshot['licenses_active'],
            'expiring': snapshot['licenses_expiring_14d'],
            'expired': snapshot['licenses_expired'],
        },
        'licenses_hero_status': build_licenses_hero_status(
            snapshot,
            renewal_breakdown=renewal_breakdown,
        ),
        'renewal_breakdown': renewal_breakdown,
        'charts': _build_charts(days),
        'licenses_hero_chart_summary': _licenses_hero_chart_summary(days, renewal_revenue),
        'licenses_revenue_chart_summary': _licenses_revenue_chart_summary(
            renewal_revenue=renewal_revenue,
            renewals=renewals,
            days=days,
        ),
        'licenses_chart_legend': LICENSES_HERO_CHART_LEGEND,
        'licenses_revenue_chart_legend': LICENSES_REVENUE_CHART_LEGEND,
        'charts_enabled': True,
        'action_items': build_licenses_action_items(snapshot),
        'expiring_licenses': expiring_list,
        'expiring_license_rows': build_expiring_license_preview_rows(expiring_list),
        'recent_renewals': recent_renewals,
        'recent_renewal_rows': recent_renewal_preview['rows'],
        'recent_renewal_summary': {
            'formal': recent_renewal_preview['formal_count'],
            'new_key': recent_renewal_preview['new_key_count'],
            'total': recent_renewal_preview['total'],
        },
        'recent_expired': recent_expired_list,
        'recent_expired_rows': recent_expired_preview['rows'],
        'recent_expired_summary': {
            'recent_7': recent_expired_preview['recent_7'],
            'recent_30': recent_expired_preview['recent_30'],
            'older': recent_expired_preview['older'],
            'total': recent_expired_preview['total'],
        },
        'users_without_license_list': without_license_list,
        'users_without_license_rows': without_license_preview['rows'],
        'users_without_license_summary': {
            'paid_buyers': without_license_preview['paid_buyers'],
            'pending_checkout': without_license_preview['pending_checkout'],
            'organic': without_license_preview['organic'],
            'total': without_license_preview['total'],
        },
        'export_links': get_licenses_export_links(),
        'snapshot_counts': snapshot,
        'table_fetch_limit': TABLE_FETCH_LIMIT,
        'table_preview_rows': TABLE_PREVIEW_ROWS,
        'marketing_url': reverse('admin_panel_marketing'),
        'users_center_url': reverse('admin_panel_users') + f'?days={days}',
    }
