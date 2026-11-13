"""مرکز کاربران — KPI، نمودار و مدیریت با بازه مرکزی Command Center."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q
from django.urls import reverse

from accounts.services.admin_presentation import prioritize_management_actions
from django.utils import timezone

from mobile_api.models import MobileDevice
from workspace.services.bot_license_query import (
    annotate_user_bot_license_access,
    users_without_bot_license_qs,
)
from accounts.services.admin_dashboard import (
    TABLE_PREVIEW_ROWS,
    _chart_day_label,
    _date_range,
    _new_users_between,
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

USERS_FOLD_ACCORDION_ROWS = 12
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

USERS_PULSE_RANGE_KEYS = (
    'users_new_period',
    'users_active_period',
    'returning_users',
    'retention_d7',
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


def _users_engagement_channel_series(days: int) -> Dict[str, List]:
    """کاربر یکتای فعال روزانه — تفکیک ورود وب و last_seen اپ."""
    start, end = _date_range(days)
    web_by_day: Dict[Any, set] = {}
    app_by_day: Dict[Any, set] = {}

    for uid, last_login in User.objects.filter(
        is_active=True,
        last_login__date__gte=start,
        last_login__date__lte=end,
    ).values_list('id', 'last_login'):
        if not last_login:
            continue
        day = last_login.date() if not timezone.is_aware(last_login) else timezone.localtime(last_login).date()
        web_by_day.setdefault(day, set()).add(uid)

    for uid, seen in MobileDevice.objects.filter(
        last_seen_at__date__gte=start,
        last_seen_at__date__lte=end,
    ).values_list('user_id', 'last_seen_at'):
        if not seen:
            continue
        day = seen.date() if not timezone.is_aware(seen) else timezone.localtime(seen).date()
        app_by_day.setdefault(day, set()).add(uid)

    labels, web_vals, app_vals, both_vals = [], [], [], []
    current = start
    while current <= end:
        labels.append(_chart_day_label(current, days))
        web_set = web_by_day.get(current, set())
        app_set = app_by_day.get(current, set())
        web_vals.append(len(web_set))
        app_vals.append(len(app_set))
        both_vals.append(len(web_set & app_set))
        current += timedelta(days=1)
    return {
        'labels': labels,
        'web': web_vals,
        'app': app_vals,
        'both': both_vals,
    }


def _users_engagement_chart_summary(channels: Dict[str, List]) -> List[Dict[str, Any]]:
    web = channels.get('web') or []
    app = channels.get('app') or []
    both = channels.get('both') or []
    n = len(web) or 1
    overlap_avg = round(sum(both) / n) if both else 0
    web_peak = max(web) if web else 0
    app_peak = max(app) if app else 0
    return [
        {
            'key': 'web_avg',
            'label': 'میانگین ورود وب',
            'value': round(sum(web) / n) if web else 0,
            'format': 'count',
        },
        {
            'key': 'app_avg',
            'label': 'میانگین فعالیت اپ',
            'value': round(sum(app) / n) if app else 0,
            'format': 'count',
        },
        {
            'key': 'overlap_avg',
            'label': 'میانگین هم‌پوشانی',
            'value': overlap_avg,
            'format': 'count',
        },
        {
            'key': 'web_peak',
            'label': 'بیشینه ورود وب',
            'value': web_peak,
            'format': 'count',
        },
        {
            'key': 'app_peak',
            'label': 'بیشینه فعالیت اپ',
            'value': app_peak,
            'format': 'count',
        },
    ]


USERS_ENGAGEMENT_CHART_LEGEND = (
    {'key': 'web', 'label': 'ورود وب'},
    {'key': 'app', 'label': 'فعالیت اپ'},
    {'key': 'both', 'label': 'هر دو کانال'},
)


def _snapshot_counts() -> Dict[str, int]:
    now = timezone.now()
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    active_qs = User.objects.filter(is_active=True)
    without_license = users_without_bot_license_qs(active_qs).count()
    users_licensed = annotate_user_bot_license_access(active_qs).filter(
        has_bot_license_access=True,
    ).count()
    idle_threshold = now - timedelta(days=30)
    inactive = active_qs.filter(
        Q(last_login__isnull=True) | Q(last_login__lt=idle_threshold),
    ).count()
    pending_payment = User.objects.filter(
        orders__status__in=PENDING_ORDER_STATUSES,
    ).distinct().count()

    return {
        'users_total': User.objects.count(),
        'users_active': active_qs.count(),
        'users_licensed': users_licensed,
        'users_without_license': without_license,
        'online_today': get_users_active_on_date(),
        'signups_today': User.objects.filter(date_joined__date=today).count(),
        'signups_yesterday': User.objects.filter(date_joined__date=yesterday).count(),
        'users_inactive': inactive,
        'users_pending_payment': pending_payment,
    }


def _users_hero_chart_summary(signups: Dict[str, List], active: Dict[str, List]) -> List[Dict[str, Any]]:
    signup_vals = signups.get('values') or []
    active_vals = active.get('values') or []
    active_len = len(active_vals) or 1
    return [
        {
            'key': 'signups_sum',
            'label': 'ثبت‌نام در بازه',
            'value': sum(signup_vals),
            'format': 'count',
        },
        {
            'key': 'active_avg',
            'label': 'میانگین فعال روزانه',
            'value': round(sum(active_vals) / active_len) if active_vals else 0,
            'format': 'count',
        },
        {
            'key': 'active_peak',
            'label': 'بیشترین فعالیت',
            'value': max(active_vals) if active_vals else 0,
            'format': 'count',
        },
    ]


def _build_users_charts(days: int) -> Dict[str, Any]:
    signups = get_user_registration_series(days)
    active = _users_active_daily_series(days)
    engagement = _build_users_engagement_chart(days)
    return {
        'user_signups': {
            'type': 'combo',
            'labels': signups['labels'],
            'hideLegend': True,
            'datasets': [
                {
                    'label': 'ثبت‌نام جدید',
                    'data': signups['values'],
                    'type': 'bar',
                    'backgroundColor': 'rgba(59, 130, 246, 0.84)',
                    'hoverBackgroundColor': 'rgba(59, 130, 246, 0.96)',
                    'borderRadius': 6,
                    'borderSkipped': False,
                    'maxBarThickness': 28,
                    'yAxisID': 'y1',
                    'order': 2,
                },
                {
                    'label': 'فعال روزانه',
                    'data': active['values'],
                    'type': 'line',
                    'borderColor': 'rgba(16, 185, 129, 1)',
                    'backgroundColor': 'rgba(16, 185, 129, 0.1)',
                    'fill': True,
                    'tension': 0.35,
                    'borderWidth': 2.5,
                    'pointRadius': 0,
                    'pointHoverRadius': 5,
                    'pointHoverBorderWidth': 2,
                    'yAxisID': 'y',
                    'order': 1,
                },
            ],
            'axis': 'count',
        },
        'users_engagement_channels': engagement,
        'users_active_trend': engagement,
    }


def _build_users_engagement_chart(days: int) -> Dict[str, Any]:
    channels = _users_engagement_channel_series(days)
    return {
        'type': 'line',
        'labels': channels['labels'],
        'hideLegend': True,
        'datasets': [
            {
                'label': 'ورود وب',
                'data': channels['web'],
                'borderColor': 'rgba(91, 79, 207, 1)',
                'backgroundColor': 'rgba(91, 79, 207, 0.08)',
                'fill': True,
                'tension': 0.38,
                'borderWidth': 2.25,
                'pointRadius': 0,
                'pointHoverRadius': 5,
                'order': 1,
            },
            {
                'label': 'فعالیت اپ',
                'data': channels['app'],
                'borderColor': 'rgba(16, 185, 129, 1)',
                'backgroundColor': 'rgba(16, 185, 129, 0.08)',
                'fill': True,
                'tension': 0.38,
                'borderWidth': 2.25,
                'pointRadius': 0,
                'pointHoverRadius': 5,
                'order': 2,
            },
            {
                'label': 'هر دو کانال',
                'data': channels['both'],
                'borderColor': 'rgba(217, 119, 6, 0.92)',
                'backgroundColor': 'rgba(217, 119, 6, 0.04)',
                'fill': False,
                'borderDash': [6, 5],
                'tension': 0.32,
                'borderWidth': 1.85,
                'pointRadius': 0,
                'pointHoverRadius': 4,
                'order': 0,
            },
        ],
        'axis': 'count',
    }


def _build_range_kpi_cards(
    *,
    days: int,
    new_users: int,
    prev_new_users: int,
    prev_prev_new_users: int | None = None,
    active_period: int,
    prev_active: int,
    retention_d7: float | None,
    retention_d30: float | None,
    retention_d7_prev: float | None = None,
    retention_d30_prev: float | None = None,
    returning_users: int,
    prev_returning: int,
) -> List[Dict[str, Any]]:
    range_label = _range_label_fa(days)
    spark = _signups_sparkline(min(days, 7))
    growth = _pct_change(new_users, prev_new_users)
    prev_growth = (
        _pct_change(prev_new_users, prev_prev_new_users)
        if prev_prev_new_users is not None
        else None
    )

    def delta(current, previous):
        return _pct_change(int(current or 0), int(previous or 0))

    def delta_percent(current: float | None, previous: float | None) -> float | None:
        if current is None or previous is None:
            return None
        return _pct_change(float(current), float(previous))

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
            'previous_value': prev_new_users,
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
            'previous_value': prev_active,
            'sparkline': spark,
            'icon': 'fa-signal',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'signup_growth_rate',
            'kind': 'range',
            'label': 'نرخ رشد ثبت‌نام',
            'sublabel': range_label,
            'value': growth if growth is not None else 0,
            'format': 'percent',
            'delta': delta_percent(growth, prev_growth) if growth is not None and prev_growth is not None else None,
            'delta_label': 'نسبت دوره قبل',
            'previous_value': prev_growth,
            'sparkline': spark,
            'icon': 'fa-chart-line',
            'accent': 'violet',
            'status': 'ok' if (growth or 0) >= 0 else 'warn',
            'pending': growth is None,
        },
        {
            'key': 'retention_d7',
            'kind': 'range',
            'label': 'بازگشت D7',
            'sublabel': 'ورود ۷+ روز پس از ثبت‌نام',
            'value': retention_d7 if retention_d7 is not None else 0,
            'format': 'percent',
            'delta': delta_percent(retention_d7, retention_d7_prev),
            'delta_label': 'نسبت دوره قبل' if retention_d7 is not None and retention_d7_prev is not None else 'کوهورت بازه',
            'previous_value': retention_d7_prev,
            'sparkline': spark,
            'icon': 'fa-user-clock',
            'accent': 'indigo',
            'status': 'ok' if retention_d7 is None or retention_d7 >= 20 else 'warn',
            'pending': retention_d7 is None,
        },
        {
            'key': 'retention_d30',
            'kind': 'range',
            'label': 'بازگشت D30',
            'sublabel': 'ورود ۳۰+ روز پس از ثبت‌نام',
            'value': retention_d30 if retention_d30 is not None else 0,
            'format': 'percent',
            'delta': delta_percent(retention_d30, retention_d30_prev),
            'delta_label': 'نسبت دوره قبل' if retention_d30 is not None and retention_d30_prev is not None else 'کوهورت بازه',
            'previous_value': retention_d30_prev,
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
            'previous_value': prev_returning,
            'sparkline': spark,
            'icon': 'fa-rotate-left',
            'accent': 'cyan',
            'status': 'ok',
        },
    ]
    return cards


def build_users_center_pulse_from_range(range_kpi_cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """۴ شاخص اصلی بازه — با دلتا نسبت دوره قبل هم‌طول."""
    by_key = {card['key']: card for card in range_kpi_cards}
    href_map = {
        'users_new_period': '#users-kpi',
        'users_active_period': '#users-charts',
        'returning_users': '#users-kpi',
        'retention_d7': '#users-kpi',
    }
    pulse: List[Dict[str, Any]] = []
    for key in USERS_PULSE_RANGE_KEYS:
        card = by_key.get(key)
        if not card:
            continue
        chip = {
            'key': key,
            'label': card['label'],
            'value': card['value'],
            'format': card['format'],
            'icon': card['icon'],
            'accent': card['accent'],
            'delta': card.get('delta'),
            'delta_label': card.get('delta_label') or 'نسبت دوره قبل',
            'previous_value': card.get('previous_value'),
            'pending': card.get('pending'),
            'href': href_map.get(key),
        }
        pulse.append(chip)
    return pulse


def _split_range_kpi_cards(
    range_kpi_cards: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    headline = [c for c in range_kpi_cards if c.get('key') in USERS_PULSE_RANGE_KEYS]
    secondary = [c for c in range_kpi_cards if c.get('key') not in USERS_PULSE_RANGE_KEYS]
    return headline, secondary


def _build_snapshot_kpi_cards(snapshot: Dict[str, int]) -> List[Dict[str, Any]]:
    spark = _signups_sparkline(7)
    return [
        {
            'key': 'users_total',
            'kind': 'snapshot',
            'label': 'کل کاربران',
            'sublabel': 'همه ثبت‌نام‌ها',
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
            'sublabel': 'حساب روشن',
            'value': snapshot['users_active'],
            'format': 'count',
            'delta': None,
            'delta_label': 'اکنون',
            'sparkline': spark,
            'icon': 'fa-user-check',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'users_without_license',
            'kind': 'snapshot',
            'label': 'بدون لایسنس',
            'sublabel': 'فعال، بدون میزکار',
            'value': snapshot['users_without_license'],
            'format': 'count',
            'delta': None,
            'delta_label': 'تبدیل',
            'sparkline': spark,
            'icon': 'fa-user-slash',
            'accent': 'rose',
            'status': 'warn' if snapshot['users_without_license'] else 'ok',
        },
        {
            'key': 'online_today',
            'kind': 'snapshot',
            'label': 'آنلاین امروز',
            'sublabel': 'وب + اپ',
            'value': snapshot.get('online_today', 0),
            'format': 'count',
            'delta': None,
            'delta_label': 'ورود امروز',
            'sparkline': spark,
            'icon': 'fa-bolt',
            'accent': 'cyan',
            'status': 'ok' if snapshot.get('online_today') else 'warn',
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
            'reason': 'حساب روشن است اما لایسنس میزکار یا ربات ندارد؛ برای تبدیل و پیگیری فروش اولویت دارد.',
            'icon': 'fa-user-slash',
            'accent': 'indigo',
            'cta': 'لیست و پرونده',
            'href': '#users-table-no-license',
        })
    if snapshot['users_inactive']:
        items.append({
            'key': 'users_inactive',
            'priority': 'medium',
            'title': 'بدون فعالیت',
            'count': snapshot['users_inactive'],
            'detail': 'بیش از ۳۰ روز بدون ورود',
            'reason': '۳۰+ روز بدون ورود وب یا فعالیت اپ؛ ریسک ریزش یا نیاز به تماس/بازگردانی.',
            'icon': 'fa-user-clock',
            'accent': 'amber',
            'cta': 'فیلتر کاربران',
            'href': '#ecc-users-mgmt',
        })
    if snapshot['users_pending_payment']:
        items.append({
            'key': 'users_pending_payment',
            'priority': 'high',
            'title': 'خرید معلق',
            'count': snapshot['users_pending_payment'],
            'detail': 'کاربر با سفارش پرداخت‌نشده',
            'reason': 'سفارش در وضعیت پرداخت‌نشده مانده؛ پیگیری فروش برای تسویه یا پیگیری مشتری.',
            'icon': 'fa-cart-shopping',
            'accent': 'violet',
            'cta': 'صف فروش',
            'href': reverse('admin_panel_sales') + '#sales-table-pending',
        })
    return prioritize_management_actions(items)


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
    span_days = (prev_end - prev_start).days + 1
    prev_prev_end = prev_start - timedelta(days=1)
    prev_prev_start = prev_prev_end - timedelta(days=span_days - 1)
    prev_prev_new_users = _new_users_between(prev_prev_start, prev_prev_end)
    active_period = _users_active_between(start, end)
    prev_active = _users_active_between(prev_start, prev_end)
    returning_users = _returning_users_between(start, end)
    prev_returning = _returning_users_between(prev_start, prev_end)
    retention_d7 = _retention_dx_in_range(start, end, 7)
    retention_d30 = _retention_dx_in_range(start, end, 30)
    retention_d7_prev = _retention_dx_in_range(prev_start, prev_end, 7)
    retention_d30_prev = _retention_dx_in_range(prev_start, prev_end, 30)

    snapshot = _snapshot_counts()
    range_kpis = _build_range_kpi_cards(
        days=days,
        new_users=new_users,
        prev_new_users=prev_new_users,
        prev_prev_new_users=prev_prev_new_users,
        active_period=active_period,
        prev_active=prev_active,
        retention_d7=retention_d7,
        retention_d30=retention_d30,
        retention_d7_prev=retention_d7_prev,
        retention_d30_prev=retention_d30_prev,
        returning_users=returning_users,
        prev_returning=prev_returning,
    )
    _, range_kpi_secondary = _split_range_kpi_cards(range_kpis)
    snapshot_kpis = _build_snapshot_kpi_cards(snapshot)
    signups_series = get_user_registration_series(days)
    active_series = _users_active_daily_series(days)
    engagement_series = _users_engagement_channel_series(days)
    charts = _build_users_charts(days)

    return {
        'chart_days': days,
        'range_label': range_label,
        'center_pulse': build_users_center_pulse_from_range(range_kpis),
        'range_kpi_cards': range_kpi_secondary,
        'range_kpi_secondary': range_kpi_secondary,
        'snapshot_kpi_cards': snapshot_kpis,
        'kpi_cards': range_kpis + snapshot_kpis,
        'charts': charts,
        'users_hero_chart_summary': _users_hero_chart_summary(signups_series, active_series),
        'users_engagement_chart_summary': _users_engagement_chart_summary(engagement_series),
        'users_engagement_legend': list(USERS_ENGAGEMENT_CHART_LEGEND),
        'charts_enabled': True,
        'action_items': build_users_action_items(snapshot),
        'recent_users': get_recent_users(limit=USERS_FOLD_ACCORDION_ROWS),
        'top_users': get_top_users_by_revenue(limit=USERS_FOLD_ACCORDION_ROWS),
        'users_without_license_list': get_users_without_license_preview(limit=USERS_FOLD_ACCORDION_ROWS),
        'users_fold_list_rows': USERS_FOLD_ACCORDION_ROWS,
        'export_links': get_users_export_links(days),
        'snapshot_counts': snapshot,
        'users_list_url': reverse('admin_panel_users_json'),
        'users_detail_url_template': reverse('admin_panel_user_detail_json', args=[0]),
    }
