"""مرکز کاربران — KPI، نمودار و مدیریت با بازه مرکزی Command Center."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone

from mobile_api.models import MobileDevice
from workspace.services.bot_license_query import users_without_bot_license_qs
from accounts.services.admin_dashboard import (
    TABLE_PREVIEW_ROWS,
    _chart_day_label,
    _date_range,
    _new_users_for_period,
    _pct_change,
    _previous_new_users_for_period,
    _previous_period_bounds,
    _range_label_fa,
    _signups_sparkline,
    get_recent_users,
    get_top_users_by_revenue,
    get_users_active_on_date,
    get_users_without_license_preview,
    get_user_registration_series,
)
from accounts.services.pending_orders import PENDING_ORDER_STATUSES
from shop.models import Order

User = get_user_model()

USERS_EXPORT_KEYS = (
    'all_users',
    'new_users',
    'users_without_license',
    'users_management',
    'users_with_pending_orders',
)


def _users_active_between(start, end) -> int:
    return (
        User.objects.filter(is_active=True)
        .filter(
            Q(last_login__date__gte=start, last_login__date__lte=end)
            | Q(mobile_devices__last_seen_at__date__gte=start, mobile_devices__last_seen_at__date__lte=end),
        )
        .distinct()
        .count()
    )


def _returning_users_between(start, end) -> int:
    return (
        User.objects.filter(is_active=True, date_joined__date__lt=start)
        .filter(
            Q(last_login__date__gte=start, last_login__date__lte=end)
            | Q(mobile_devices__last_seen_at__date__gte=start, mobile_devices__last_seen_at__date__lte=end),
        )
        .distinct()
        .count()
    )


def _retention_dx_in_range(start, end, window_days: int) -> float | None:
    """نرخ بازگشت D7/D30 برای کوهورت ثبت‌نام‌شده در بازه."""
    cohort_end = end - timedelta(days=window_days)
    if cohort_end < start:
        return None
    cohort = list(
        User.objects.filter(
            is_active=True,
            date_joined__date__gte=start,
            date_joined__date__lte=cohort_end,
        ).values_list('id', 'date_joined', 'last_login')
    )
    if not cohort:
        return None
    retained = 0
    user_ids = [row[0] for row in cohort]
    mobile_by_user: Dict[int, set] = {}
    for row in MobileDevice.objects.filter(user_id__in=user_ids).values_list('user_id', 'last_seen_at'):
        if not row[1]:
            continue
        seen = row[1].date() if not timezone.is_aware(row[1]) else timezone.localtime(row[1]).date()
        mobile_by_user.setdefault(row[0], set()).add(seen)

    for uid, joined, last_login in cohort:
        jd = joined.date() if not timezone.is_aware(joined) else timezone.localtime(joined).date()
        check_from = max(jd + timedelta(days=window_days), start)
        if check_from > end:
            continue
        if last_login:
            ll = last_login.date() if not timezone.is_aware(last_login) else timezone.localtime(last_login).date()
            if ll >= check_from:
                retained += 1
                continue
        if any(d >= check_from for d in mobile_by_user.get(uid, ())):
            retained += 1
    return round((retained / len(cohort)) * 100, 1)


def _users_active_daily_series(days: int) -> Dict[str, List]:
    start, end = _date_range(days)
    day_users: Dict[Any, set] = {}
    for uid, last_login in User.objects.filter(
        is_active=True,
        last_login__date__gte=start,
        last_login__date__lte=end,
    ).values_list('id', 'last_login'):
        if not last_login:
            continue
        day = last_login.date() if not timezone.is_aware(last_login) else timezone.localtime(last_login).date()
        day_users.setdefault(day, set()).add(uid)

    for uid, seen in MobileDevice.objects.filter(
        last_seen_at__date__gte=start,
        last_seen_at__date__lte=end,
    ).values_list('user_id', 'last_seen_at'):
        if not seen:
            continue
        day = seen.date() if not timezone.is_aware(seen) else timezone.localtime(seen).date()
        day_users.setdefault(day, set()).add(uid)

    labels, values = [], []
    current = start
    while current <= end:
        labels.append(_chart_day_label(current, days))
        values.append(len(day_users.get(current, set())))
        current += timedelta(days=1)
    return {'labels': labels, 'values': values}


def _snapshot_counts() -> Dict[str, int]:
    now = timezone.now()
    without_license = users_without_bot_license_qs(
        User.objects.filter(is_active=True),
    ).count()
    idle_threshold = now - timedelta(days=30)
    inactive = User.objects.filter(is_active=True).filter(
        Q(last_login__isnull=True) | Q(last_login__lt=idle_threshold),
    ).count()
    pending_payment = User.objects.filter(
        orders__status__in=PENDING_ORDER_STATUSES,
    ).distinct().count()

    return {
        'users_total': User.objects.count(),
        'users_active': User.objects.filter(is_active=True).count(),
        'users_without_license': without_license,
        'online_today': get_users_active_on_date(),
        'users_inactive': inactive,
        'users_pending_payment': pending_payment,
    }


def _build_users_charts(days: int) -> Dict[str, Any]:
    signups = get_user_registration_series(days)
    active = _users_active_daily_series(days)
    return {
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
        'users_active_trend': {
            'type': 'line',
            'labels': active['labels'],
            'datasets': [{
                'label': 'کاربران فعال روزانه',
                'data': active['values'],
                'borderColor': 'rgba(16, 185, 129, 1)',
                'backgroundColor': 'rgba(16, 185, 129, 0.12)',
                'fill': True,
                'tension': 0.35,
            }],
            'axis': 'count',
        },
    }


def _build_range_kpi_cards(
    *,
    days: int,
    new_users: int,
    prev_new_users: int,
    active_period: int,
    prev_active: int,
    retention_d7: float | None,
    retention_d30: float | None,
    returning_users: int,
    prev_returning: int,
) -> List[Dict[str, Any]]:
    range_label = _range_label_fa(days)
    spark = _signups_sparkline(min(days, 7))
    growth = _pct_change(new_users, prev_new_users)

    def delta(current, previous):
        return _pct_change(int(current or 0), int(previous or 0))

    cards = [
        {
            'key': 'users_new_period',
            'kind': 'range',
            'label': 'کاربران جدید',
            'sublabel': range_label,
            'value': new_users,
            'format': 'count',
            'delta': delta(new_users, prev_new_users),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark,
            'icon': 'fa-user-plus',
            'accent': 'blue',
            'status': 'ok',
        },
        {
            'key': 'users_active_period',
            'kind': 'range',
            'label': 'فعال در بازه',
            'sublabel': range_label,
            'value': active_period,
            'format': 'count',
            'delta': delta(active_period, prev_active),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark,
            'icon': 'fa-signal',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'signup_growth_rate',
            'kind': 'range',
            'label': 'نرخ رشد ثبت‌نام',
            'sublabel': 'نسبت دوره قبل',
            'value': growth if growth is not None else 0,
            'format': 'percent',
            'delta': None,
            'delta_label': range_label,
            'sparkline': spark,
            'icon': 'fa-chart-line',
            'accent': 'violet',
            'status': 'ok' if (growth or 0) >= 0 else 'warn',
        },
        {
            'key': 'retention_d7',
            'kind': 'range',
            'label': 'Retention D7',
            'sublabel': range_label,
            'value': retention_d7 if retention_d7 is not None else 0,
            'format': 'percent',
            'delta': None,
            'delta_label': 'کوهورت بازه' if retention_d7 is not None else 'داده ناکافی',
            'sparkline': spark,
            'icon': 'fa-user-clock',
            'accent': 'indigo',
            'status': 'ok' if retention_d7 is None or retention_d7 >= 20 else 'warn',
            'pending': retention_d7 is None,
        },
        {
            'key': 'retention_d30',
            'kind': 'range',
            'label': 'Retention D30',
            'sublabel': range_label,
            'value': retention_d30 if retention_d30 is not None else 0,
            'format': 'percent',
            'delta': None,
            'delta_label': 'کوهورت بازه' if retention_d30 is not None else 'داده ناکافی',
            'sparkline': spark,
            'icon': 'fa-user-clock',
            'accent': 'amber',
            'status': 'ok' if retention_d30 is None or retention_d30 >= 20 else 'warn',
            'pending': retention_d30 is None,
        },
        {
            'key': 'returning_users',
            'kind': 'range',
            'label': 'کاربران برگشتی',
            'sublabel': 'فعال · عضو قبلی',
            'value': returning_users,
            'format': 'count',
            'delta': delta(returning_users, prev_returning),
            'delta_label': 'نسبت دوره قبل',
            'sparkline': spark,
            'icon': 'fa-rotate-left',
            'accent': 'cyan',
            'status': 'ok',
        },
    ]
    return cards


def _build_snapshot_kpi_cards(snapshot: Dict[str, int]) -> List[Dict[str, Any]]:
    spark = _signups_sparkline(7)
    return [
        {
            'key': 'users_total',
            'kind': 'snapshot',
            'label': 'کل کاربران',
            'sublabel': 'Snapshot',
            'value': snapshot['users_total'],
            'format': 'count',
            'delta': None,
            'delta_label': 'همه زمان',
            'sparkline': spark,
            'icon': 'fa-users',
            'accent': 'indigo',
            'status': 'ok',
        },
        {
            'key': 'users_active_current',
            'kind': 'snapshot',
            'label': 'کاربران فعال',
            'sublabel': 'حساب فعال',
            'value': snapshot['users_active'],
            'format': 'count',
            'delta': None,
            'delta_label': 'Snapshot',
            'sparkline': spark,
            'icon': 'fa-user-check',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'users_without_license',
            'kind': 'snapshot',
            'label': 'بدون لایسنس',
            'sublabel': 'Snapshot',
            'value': snapshot['users_without_license'],
            'format': 'count',
            'delta': None,
            'delta_label': 'نیازمند تبدیل',
            'sparkline': spark,
            'icon': 'fa-user-slash',
            'accent': 'rose',
            'status': 'warn' if snapshot['users_without_license'] else 'ok',
        },
        {
            'key': 'online_today',
            'kind': 'snapshot',
            'label': 'آنلاین امروز',
            'sublabel': 'Snapshot',
            'value': snapshot['online_today'],
            'format': 'count',
            'delta': None,
            'delta_label': 'وب + اپ',
            'sparkline': spark,
            'icon': 'fa-circle',
            'accent': 'cyan',
            'status': 'ok',
        },
    ]


def build_users_action_items(snapshot: Dict[str, int]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if snapshot['users_without_license']:
        items.append({
            'key': 'users_without_license',
            'priority': 'high',
            'title': 'بدون لایسنس فعال',
            'count': snapshot['users_without_license'],
            'detail': 'کاربران فعال بدون لایسنس',
            'icon': 'fa-user-slash',
            'accent': 'indigo',
            'cta': 'مشاهده',
            'href': '#users-table-no-license',
        })
    if snapshot['users_inactive']:
        items.append({
            'key': 'users_inactive',
            'priority': 'medium',
            'title': 'بدون فعالیت',
            'count': snapshot['users_inactive'],
            'detail': 'بیش از ۳۰ روز بدون ورود',
            'icon': 'fa-user-clock',
            'accent': 'amber',
            'cta': 'فیلتر',
            'href': '#ecc-users-mgmt',
        })
    if snapshot['users_pending_payment']:
        items.append({
            'key': 'users_pending_payment',
            'priority': 'high',
            'title': 'خرید معلق',
            'count': snapshot['users_pending_payment'],
            'detail': 'کاربر با سفارش پرداخت‌نشده',
            'icon': 'fa-cart-shopping',
            'accent': 'violet',
            'cta': 'فروش',
            'href': reverse('admin_panel_sales') + '#sales-table-pending',
        })
    return items


def get_users_export_links(days: int) -> List[Dict[str, Any]]:
    from accounts.services.admin_exports import EXPORT_REGISTRY, get_export_count

    links = []
    for key in USERS_EXPORT_KEYS:
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
            + (f'?format=xlsx&days={days}' if meta.get('supports_days') else '?format=xlsx'),
        })
    return links


def get_users_center_context(*, days: int = 30, compare: bool = False) -> Dict[str, Any]:
    del compare

    start, end = _date_range(days)
    prev_start, prev_end = _previous_period_bounds(days)
    range_label = _range_label_fa(days)

    new_users = _new_users_for_period(days)
    prev_new_users = _previous_new_users_for_period(days)
    active_period = _users_active_between(start, end)
    prev_active = _users_active_between(prev_start, prev_end)
    returning_users = _returning_users_between(start, end)
    prev_returning = _returning_users_between(prev_start, prev_end)
    retention_d7 = _retention_dx_in_range(start, end, 7)
    retention_d30 = _retention_dx_in_range(start, end, 30)

    snapshot = _snapshot_counts()
    range_kpis = _build_range_kpi_cards(
        days=days,
        new_users=new_users,
        prev_new_users=prev_new_users,
        active_period=active_period,
        prev_active=prev_active,
        retention_d7=retention_d7,
        retention_d30=retention_d30,
        returning_users=returning_users,
        prev_returning=prev_returning,
    )
    snapshot_kpis = _build_snapshot_kpi_cards(snapshot)

    return {
        'chart_days': days,
        'range_label': range_label,
        'range_kpi_cards': range_kpis,
        'snapshot_kpi_cards': snapshot_kpis,
        'kpi_cards': range_kpis + snapshot_kpis,
        'charts': _build_users_charts(days),
        'action_items': build_users_action_items(snapshot),
        'recent_users': get_recent_users(limit=TABLE_PREVIEW_ROWS),
        'top_users': get_top_users_by_revenue(limit=TABLE_PREVIEW_ROWS),
        'users_without_license_list': get_users_without_license_preview(limit=TABLE_PREVIEW_ROWS),
        'export_links': get_users_export_links(days),
        'snapshot_counts': snapshot,
        'users_list_url': reverse('admin_panel_users_json'),
        'users_detail_url_template': reverse('admin_panel_user_detail_json', args=[0]),
    }
