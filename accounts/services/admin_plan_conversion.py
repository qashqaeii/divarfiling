"""آنالیز نرخ تبدیل پلن‌ها برای پنل مدیریت — اعداد دقیق + تاریخ شمسی."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import jdatetime
from django.db.models import Count, Min, Q, Sum
from django.db.models.functions import Coalesce, TruncDate, TruncWeek
from django.utils import timezone

from accounts.services.admin_dashboard import (
    PLAN_CHART_COLORS,
    PLAN_TYPE_ACCENTS,
    PLAN_TYPE_SHORT_LABELS,
    _plan_short_label,
    get_plan_sales_breakdown,
)
from shop.models import LicensePlan, Order, PlanFunnelEvent
from workspace.services.jalali_input import PERSIAN_MONTHS, to_persian_digits


UPGRADE_WINDOW_DAYS = 7


def _clamp_days(days: int) -> int:
    return max(7, min(int(days), 365))


def _pct(numerator: int | float, denominator: int | float, places: int = 2) -> float:
    """درصد دقیق با گرد کردن HALF_UP."""
    if not denominator:
        return 0.0
    q = Decimal('0.1') ** places
    value = (Decimal(numerator) * Decimal(100) / Decimal(denominator)).quantize(q, rounding=ROUND_HALF_UP)
    return float(value)


def _to_local_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _jalali_day_label(day: date, *, compact: bool = False) -> str:
    j = jdatetime.date.fromgregorian(date=day)
    if compact:
        return to_persian_digits(f'{j.day:02d}/{j.month:02d}')
    month = PERSIAN_MONTHS[j.month - 1]
    return to_persian_digits(f'{j.day} {month}')


def _jalali_week_label(week_start: date) -> str:
    """برچسب هفته شمسی — مثال: هفته ۰۱ تیر ۱۴۰۵"""
    j = jdatetime.date.fromgregorian(date=week_start)
    month = PERSIAN_MONTHS[j.month - 1]
    return to_persian_digits(f'هفته {j.day:02d} {month} {j.year}')


def _jalali_iso(day: date) -> str:
    j = jdatetime.date.fromgregorian(date=day)
    return to_persian_digits(j.strftime('%Y/%m/%d'))


def _week_start_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _paid_orders_qs(*, since=None):
    """سفارش‌های پرداخت‌شده — paid_at در اولویت، وگرنه created_at."""
    qs = (
        Order.objects.filter(status='paid')
        .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
        .select_related('plan', 'product', 'user')
    )
    if since is not None:
        qs = qs.filter(effective_paid__gte=since)
    return qs


def _funnel_events_since(since, event_type: str):
    return PlanFunnelEvent.objects.filter(event_type=event_type, created_at__gte=since)


def count_daily_to_monthly_upgrades(*, since=None, window_days: int = UPGRADE_WINDOW_DAYS) -> dict[str, Any]:
    """کاربران یکتای خریدار پلن روزانه که ظرف window_days به ماهانه ارتقا داده‌اند."""
    daily_qs = (
        Order.objects.filter(status='paid', plan__plan_type='daily')
        .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
        .filter(effective_paid__isnull=False)
        .select_related('user', 'plan')
        .order_by('user_id', 'effective_paid')
    )
    if since is not None:
        daily_qs = daily_qs.filter(effective_paid__gte=since)

    first_daily_by_user: dict[int, datetime] = {}
    for order in daily_qs.iterator():
        uid = order.user_id
        if uid not in first_daily_by_user:
            first_daily_by_user[uid] = order.effective_paid

    upgraded_users: set[int] = set()
    window = timedelta(days=window_days)

    for user_id, first_paid in first_daily_by_user.items():
        upgraded = Order.objects.filter(
            user_id=user_id,
            status='paid',
            plan__plan_type='monthly',
        ).annotate(
            effective_paid=Coalesce('paid_at', 'created_at'),
        ).filter(
            effective_paid__gt=first_paid,
            effective_paid__lte=first_paid + window,
        ).exists()
        if upgraded:
            upgraded_users.add(user_id)

    daily_buyers = len(first_daily_by_user)
    upgrade_count = len(upgraded_users)
    return {
        'daily_buyers': daily_buyers,
        'upgrade_count': upgrade_count,
        'upgrade_rate': _pct(upgrade_count, daily_buyers, 1),
        'window_days': window_days,
    }


def get_plan_conversion_by_plan(*, since, pricing_views: int, checkout_views: int) -> list[dict[str, Any]]:
    """فروش و تبدیل هر پلن فعال — تجمیع بر اساس product + plan_type."""
    sales_by_key: dict[tuple, dict[str, int]] = {}
    sales_rows = (
        _paid_orders_qs(since=since)
        .filter(plan_id__isnull=False)
        .values('plan__product_id', 'plan__plan_type')
        .annotate(count=Count('id'), total=Sum('amount'))
    )
    for row in sales_rows:
        key = (row['plan__product_id'], row['plan__plan_type'] or '')
        sales_by_key[key] = {
            'count': int(row['count'] or 0),
            'total': int(row['total'] or 0),
        }

    total_count = sum(item['count'] for item in sales_by_key.values())
    total_revenue = sum(item['total'] for item in sales_by_key.values())

    plans = (
        LicensePlan.objects.filter(is_active=True)
        .select_related('product')
        .order_by('order', 'price', 'id')
    )
    seen: set[tuple] = set()
    rows: list[dict[str, Any]] = []

    for plan in plans:
        key = (plan.product_id, plan.plan_type or '')
        if key in seen:
            continue
        seen.add(key)

        stats = sales_by_key.get(key, {'count': 0, 'total': 0})
        count = stats['count']
        total = stats['total']
        rows.append({
            'plan_id': plan.id,
            'product_id': plan.product_id,
            'product_title': plan.product.title,
            'plan_type': plan.plan_type,
            'label': plan.name,
            'full_label': f'{plan.product.title} — {plan.name}',
            'short_label': _plan_short_label(plan),
            'accent': PLAN_TYPE_ACCENTS.get(plan.plan_type, 'violet'),
            'price': int(plan.price or 0),
            'purchases': count,
            'revenue': total,
            'order_share': _pct(count, total_count, 1),
            'revenue_share': _pct(total, total_revenue, 1),
            'funnel_conversion': _pct(count, pricing_views, 2),
            'checkout_conversion': _pct(count, checkout_views, 2),
            'aov': int(round(total / count)) if count else 0,
        })

    return rows


def get_weekly_purchase_series(*, since, weeks: int = 16) -> list[dict[str, Any]]:
    rows = (
        _paid_orders_qs(since=since)
        .annotate(week=TruncWeek('effective_paid'))
        .values('week')
        .annotate(
            total=Count('id'),
            daily=Count('id', filter=Q(plan__plan_type='daily')),
            monthly=Count('id', filter=Q(plan__plan_type='monthly')),
            quarterly=Count('id', filter=Q(plan__plan_type='quarterly')),
            yearly=Count('id', filter=Q(plan__plan_type='yearly')),
            revenue=Sum('amount'),
        )
        .order_by('week')
    )
    series = []
    for row in rows:
        if not row['week']:
            continue
        week_dt = row['week']
        if timezone.is_aware(week_dt):
            week_dt = timezone.localtime(week_dt)
        week_date = week_dt.date() if isinstance(week_dt, datetime) else week_dt
        series.append({
            'week': week_date.isoformat(),
            'week_jalali': _jalali_iso(week_date),
            'week_label': _jalali_week_label(week_date),
            'total': int(row['total'] or 0),
            'daily': int(row['daily'] or 0),
            'monthly': int(row['monthly'] or 0),
            'quarterly': int(row['quarterly'] or 0),
            'yearly': int(row['yearly'] or 0),
            'revenue': int(row['revenue'] or 0),
        })
    return series[-weeks:]


def get_purchase_cohorts(*, limit: int = 12) -> list[dict[str, Any]]:
    """کوهورت بر اساس هفته اولین خرید پرداخت‌شده."""
    first_paid_rows = (
        Order.objects.filter(status='paid')
        .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
        .filter(effective_paid__isnull=False)
        .values('user_id')
        .annotate(first_paid=Min('effective_paid'))
        .order_by('-first_paid')[:8000]
    )

    cohorts: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'users': 0,
        'repeat_7d': 0,
        'repeat_30d': 0,
        'upgraded_monthly_7d': 0,
        'revenue': 0,
        'daily_starters': 0,
    })

    window_7 = timedelta(days=7)
    window_30 = timedelta(days=30)

    for row in first_paid_rows:
        user_id = row['user_id']
        first_paid = row['first_paid']
        first_date = _to_local_date(first_paid)
        if not first_date:
            continue
        week_start = _week_start_monday(first_date)
        key = week_start.isoformat()

        bucket = cohorts[key]
        bucket['users'] += 1

        user_orders = (
            Order.objects.filter(user_id=user_id, status='paid')
            .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
            .filter(effective_paid__isnull=False)
            .select_related('plan')
        )
        user_revenue = user_orders.aggregate(total=Sum('amount'))['total'] or 0
        bucket['revenue'] += int(user_revenue)

        if user_orders.filter(
            effective_paid__gt=first_paid,
            effective_paid__lte=first_paid + window_7,
        ).exists():
            bucket['repeat_7d'] += 1

        if user_orders.filter(
            effective_paid__gt=first_paid,
            effective_paid__lte=first_paid + window_30,
        ).exists():
            bucket['repeat_30d'] += 1

        first_order = user_orders.order_by('effective_paid').first()
        if first_order and first_order.plan and first_order.plan.plan_type == 'daily':
            bucket['daily_starters'] += 1
            if user_orders.filter(
                plan__plan_type='monthly',
                effective_paid__gt=first_paid,
                effective_paid__lte=first_paid + window_7,
            ).exists():
                bucket['upgraded_monthly_7d'] += 1

    result = []
    for week_key in sorted(cohorts.keys(), reverse=True)[:limit]:
        data = cohorts[week_key]
        users = data['users']
        week_date = date.fromisoformat(week_key)
        daily_starters = data['daily_starters']
        result.append({
            'week': week_key,
            'week_jalali': _jalali_iso(week_date),
            'week_label': _jalali_week_label(week_date),
            'users': users,
            'daily_starters': daily_starters,
            'repeat_7d': data['repeat_7d'],
            'repeat_30d': data['repeat_30d'],
            'repeat_7d_rate': _pct(data['repeat_7d'], users, 1),
            'repeat_30d_rate': _pct(data['repeat_30d'], users, 1),
            'upgraded_monthly_7d': data['upgraded_monthly_7d'],
            'upgrade_rate': _pct(data['upgraded_monthly_7d'], daily_starters or users, 1),
            'upgrade_rate_of_all': _pct(data['upgraded_monthly_7d'], users, 1),
            'avg_ltv': int(round(data['revenue'] / users)) if users else 0,
            'revenue': int(data['revenue']),
        })
    return result


def get_funnel_daily_series(*, since, days: int) -> dict[str, list]:
    """سری روزانه کامل با صفر برای روزهای خالی + برچسب شمسی."""
    end = timezone.localdate()
    start = end - timedelta(days=days - 1)

    def _lookup(qs, date_field: str) -> dict[date, int]:
        rows = (
            qs.annotate(day=TruncDate(date_field))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        out: dict[date, int] = {}
        for r in rows:
            if r['day']:
                d = r['day']
                out[d if isinstance(d, date) else d] = int(r['count'] or 0)
        return out

    pricing_map = _lookup(_funnel_events_since(since, 'pricing_view'), 'created_at')
    checkout_map = _lookup(_funnel_events_since(since, 'checkout_view'), 'created_at')
    purchase_map = _lookup(_paid_orders_qs(since=since), 'effective_paid')

    labels: list[str] = []
    labels_full: list[str] = []
    iso_days: list[str] = []
    pricing_counts: list[int] = []
    checkout_counts: list[int] = []
    purchase_counts: list[int] = []

    current = start
    while current <= end:
        labels.append(_jalali_day_label(current, compact=True))
        labels_full.append(_jalali_iso(current))
        iso_days.append(current.isoformat())
        pricing_counts.append(pricing_map.get(current, 0))
        checkout_counts.append(checkout_map.get(current, 0))
        purchase_counts.append(purchase_map.get(current, 0))
        current += timedelta(days=1)

    return {
        'labels': labels,
        'labels_full': labels_full,
        'iso_days': iso_days,
        'pricing_counts': pricing_counts,
        'checkout_counts': checkout_counts,
        'purchase_counts': purchase_counts,
        # سازگاری با نسخه قبلی
        'pricing_labels': labels,
        'checkout_labels': labels,
        'purchase_labels': labels,
    }


def build_plan_conversion_chart_payload(
    *,
    plan_rows: list[dict[str, Any]],
    weekly_series: list[dict[str, Any]],
    funnel_series: dict[str, list],
    cohorts: list[dict[str, Any]],
) -> dict[str, Any]:
    colors = [PLAN_CHART_COLORS[i % len(PLAN_CHART_COLORS)] for i in range(len(plan_rows))]

    return {
        'funnel_daily': funnel_series,
        'plan_share': {
            'labels': [row['short_label'] for row in plan_rows],
            'full_labels': [row.get('full_label') or row['label'] for row in plan_rows],
            'values': [row['revenue_share'] for row in plan_rows],
            'order_share': [row['order_share'] for row in plan_rows],
            'revenue': [row['revenue'] for row in plan_rows],
            'purchases': [row['purchases'] for row in plan_rows],
            'aov': [row.get('aov', 0) for row in plan_rows],
            'colors': colors,
        },
        'plan_conversion': {
            'labels': [row['short_label'] for row in plan_rows],
            'funnel_rates': [row['funnel_conversion'] for row in plan_rows],
            'checkout_rates': [row['checkout_conversion'] for row in plan_rows],
            'purchases': [row['purchases'] for row in plan_rows],
            'accents': [row['accent'] for row in plan_rows],
            'colors': colors,
        },
        'weekly_purchases': {
            'labels': [row['week_label'] for row in weekly_series],
            'labels_short': [row['week_jalali'] for row in weekly_series],
            'iso_weeks': [row['week'] for row in weekly_series],
            'total': [row['total'] for row in weekly_series],
            'daily': [row['daily'] for row in weekly_series],
            'monthly': [row['monthly'] for row in weekly_series],
            'quarterly': [row['quarterly'] for row in weekly_series],
            'yearly': [row['yearly'] for row in weekly_series],
            'revenue': [row['revenue'] for row in weekly_series],
        },
        'cohort': {
            'labels': [c['week_label'] for c in cohorts],
            'labels_jalali': [c['week_jalali'] for c in cohorts],
            'users': [c['users'] for c in cohorts],
            'repeat_7d_rate': [c['repeat_7d_rate'] for c in cohorts],
            'repeat_30d_rate': [c['repeat_30d_rate'] for c in cohorts],
            'upgrade_rate': [c['upgrade_rate'] for c in cohorts],
            'avg_ltv': [c['avg_ltv'] for c in cohorts],
        },
    }


def get_plan_conversion_context(*, days: int = 30) -> dict[str, Any]:
    days = _clamp_days(days)
    now = timezone.now()
    since = now - timedelta(days=days)
    period_start = timezone.localdate() - timedelta(days=days - 1)
    period_end = timezone.localdate()

    pricing_views = _funnel_events_since(since, 'pricing_view').count()
    pricing_unique = (
        _funnel_events_since(since, 'pricing_view')
        .exclude(session_key='')
        .values('session_key')
        .distinct()
        .count()
    )
    checkout_views = _funnel_events_since(since, 'checkout_view').count()
    upgrade_views = _funnel_events_since(since, 'upgrade_view').count()

    paid_qs = _paid_orders_qs(since=since)
    paid_count = paid_qs.count()
    paid_revenue = int(paid_qs.aggregate(total=Sum('amount'))['total'] or 0)
    daily_purchases = paid_qs.filter(plan__plan_type='daily').count()
    monthly_purchases = paid_qs.filter(plan__plan_type='monthly').count()
    quarterly_purchases = paid_qs.filter(plan__plan_type='quarterly').count()
    yearly_purchases = paid_qs.filter(plan__plan_type='yearly').count()
    unique_buyers = paid_qs.values('user_id').distinct().count()
    aov = int(round(paid_revenue / paid_count)) if paid_count else 0

    upgrade_stats = count_daily_to_monthly_upgrades(since=since)

    overall_conversion = _pct(paid_count, pricing_views, 2)
    unique_conversion = _pct(paid_count, pricing_unique, 2)
    checkout_conversion = _pct(paid_count, checkout_views, 2)
    pricing_to_checkout = _pct(checkout_views, pricing_views, 1)
    checkout_to_paid = _pct(paid_count, checkout_views, 1)

    plan_rows = get_plan_conversion_by_plan(
        since=since,
        pricing_views=pricing_views,
        checkout_views=checkout_views,
    )
    weekly_series = get_weekly_purchase_series(since=since)
    cohorts = get_purchase_cohorts(limit=12)
    funnel_series = get_funnel_daily_series(since=since, days=days)

    charts = build_plan_conversion_chart_payload(
        plan_rows=plan_rows,
        weekly_series=weekly_series,
        funnel_series=funnel_series,
        cohorts=cohorts,
    )

    plan_sales_all_time = get_plan_sales_breakdown()

    summary = {
        'pricing_views': pricing_views,
        'pricing_unique': pricing_unique,
        'checkout_views': checkout_views,
        'upgrade_views': upgrade_views,
        'paid_count': paid_count,
        'paid_revenue': paid_revenue,
        'daily_purchases': daily_purchases,
        'monthly_purchases': monthly_purchases,
        'quarterly_purchases': quarterly_purchases,
        'yearly_purchases': yearly_purchases,
        'unique_buyers': unique_buyers,
        'aov': aov,
        'overall_conversion': overall_conversion,
        'unique_conversion': unique_conversion,
        'checkout_conversion': checkout_conversion,
        'upgrade_count': upgrade_stats['upgrade_count'],
        'upgrade_rate': upgrade_stats['upgrade_rate'],
        'daily_buyers_for_upgrade': upgrade_stats['daily_buyers'],
        'upgrade_window_days': upgrade_stats['window_days'],
        'funnel_stages': {
            'pricing_to_checkout': pricing_to_checkout,
            'checkout_to_paid': checkout_to_paid,
            'pricing_to_paid': overall_conversion,
        },
        'dropoffs': {
            'pricing_to_checkout': _pct(
                max(pricing_views - checkout_views, 0), pricing_views, 1,
            ) if pricing_views else 0.0,
            'checkout_to_paid': _pct(
                max(checkout_views - paid_count, 0), checkout_views, 1,
            ) if checkout_views else 0.0,
        },
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
        'period_start_jalali': _jalali_iso(period_start),
        'period_end_jalali': _jalali_iso(period_end),
        'generated_at': now.isoformat(),
        'generated_at_jalali': to_persian_digits(
            jdatetime.datetime.fromgregorian(
                datetime=timezone.localtime(now),
            ).strftime('%Y/%m/%d %H:%M'),
        ),
    }

    return {
        'days': days,
        'summary': summary,
        'plan_rows': plan_rows,
        'weekly_series': weekly_series,
        'cohorts': cohorts,
        'plan_sales_all_time': plan_sales_all_time,
        'plan_type_labels': PLAN_TYPE_SHORT_LABELS,
        'charts': charts,
    }


def build_plan_conversion_json(*, days: int = 30) -> dict[str, Any]:
    """خروجی کامل JSON برای دانلود / API."""
    ctx = get_plan_conversion_context(days=days)
    return {
        'ok': True,
        'meta': {
            'days': ctx['days'],
            'period_start': ctx['summary']['period_start'],
            'period_end': ctx['summary']['period_end'],
            'period_start_jalali': ctx['summary']['period_start_jalali'],
            'period_end_jalali': ctx['summary']['period_end_jalali'],
            'generated_at': ctx['summary']['generated_at'],
            'generated_at_jalali': ctx['summary']['generated_at_jalali'],
            'source': 'admin_panel_plan_conversion',
            'version': '1.1',
        },
        'summary': ctx['summary'],
        'plans': ctx['plan_rows'],
        'weekly': ctx['weekly_series'],
        'cohorts': ctx['cohorts'],
        'charts': ctx['charts'],
        'plan_sales_all_time': ctx['plan_sales_all_time'],
    }
