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

User = get_user_model()

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
        return _pct_change(int(current or 0), int(previous or 0))

    return [
        {
            'key': 'licenses_new_period',
            'kind': 'range',
            'label': 'لایسنس جدید',
            'sublabel': range_label,
            'value': licenses_new,
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
            'format': 'percent',
            'delta': _pct_change(renewal_rate, prev_renewal_rate),
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


def build_licenses_center_pulse(snapshot: Dict[str, int]) -> List[Dict[str, Any]]:
    return [
        {
            'label': 'لایسنس فعال',
            'value': snapshot.get('licenses_active', 0),
            'format': 'count',
            'href': '#licenses-kpi',
        },
        {
            'label': 'انقضا ≤۷ روز',
            'value': snapshot.get('licenses_expiring_7d', 0),
            'format': 'count',
            'href': '#licenses-table-expiring',
        },
        {
            'label': 'منقضی',
            'value': snapshot.get('licenses_expired', 0),
            'format': 'count',
            'href': '#licenses-table-expired',
        },
        {
            'label': 'فعال‌سازی دستگاه',
            'value': snapshot.get('active_devices', 0),
            'format': 'count',
            'hint': 'Activation',
        },
        {
            'label': 'کاربر بدون لایسنس',
            'value': snapshot.get('users_without_license', 0),
            'format': 'count',
            'href': reverse('admin_panel_users') + '#users-table-no-license',
        },
    ]


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
            'icon': 'fa-hourglass-half',
            'accent': 'amber',
            'cta': 'مشاهده',
            'href': '#licenses-table-expiring',
        })
    if snapshot['licenses_expired']:
        items.append({
            'key': 'licenses_expired',
            'priority': 'medium',
            'title': 'لایسنس منقضی',
            'count': snapshot['licenses_expired'],
            'detail': 'نیاز به پیگیری تمدید',
            'icon': 'fa-ban',
            'accent': 'rose',
            'cta': 'مشاهده',
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
            'icon': 'fa-user-slash',
            'accent': 'indigo',
            'cta': 'کمپین تمدید',
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

    recent_renewals = get_recent_renewal_orders(limit=TABLE_PREVIEW_ROWS)
    renewal_breakdown = {
        'formal_renewals_range': formal_renewals,
        'new_key_repurchase_range': new_key_repurchase,
        'renewal_revenue_range': renewal_revenue,
        'renewal_rate_range': renewal_rate,
    }

    return {
        'chart_days': days,
        'range_label': range_label,
        'center_pulse': build_licenses_center_pulse(snapshot),
        'range_kpi_cards': range_kpis,
        'snapshot_kpi_cards': snapshot_kpis,
        'kpi_cards': range_kpis + snapshot_kpis,
        'status_distribution': {
            'active': snapshot['licenses_active'],
            'expiring': snapshot['licenses_expiring_14d'],
            'expired': snapshot['licenses_expired'],
        },
        'renewal_breakdown': renewal_breakdown,
        'charts': _build_charts(days),
        'charts_enabled': True,
        'action_items': build_licenses_action_items(snapshot),
        'expiring_licenses': get_expiring_licenses(limit=TABLE_PREVIEW_ROWS),
        'recent_renewals': recent_renewals,
        'recent_expired': get_recent_expired_licenses(limit=TABLE_PREVIEW_ROWS),
        'users_without_license_list': get_users_without_license_preview(limit=TABLE_PREVIEW_ROWS),
        'export_links': get_licenses_export_links(),
        'snapshot_counts': snapshot,
        'table_fetch_limit': TABLE_FETCH_LIMIT,
        'table_preview_rows': TABLE_PREVIEW_ROWS,
        'marketing_url': reverse('admin_panel_marketing'),
        'users_center_url': reverse('admin_panel_users') + f'?days={days}',
    }
