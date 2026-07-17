"""آنالیز نرخ تبدیل پلن‌ها برای پنل مدیریت."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import Count, Min, Q, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from accounts.services.admin_dashboard import (
    PLAN_CHART_COLORS,
    PLAN_TYPE_ACCENTS,
    PLAN_TYPE_SHORT_LABELS,
    _plan_short_label,
    get_plan_sales_breakdown,
)
from shop.models import LicensePlan, Order, PlanFunnelEvent


UPGRADE_WINDOW_DAYS = 7


def _clamp_days(days: int) -> int:
    return max(7, min(int(days), 365))


def _paid_orders_since(since):
    return Order.objects.filter(status='paid', paid_at__gte=since).select_related('plan', 'product')


def _funnel_events_since(since, event_type: str):
    return PlanFunnelEvent.objects.filter(event_type=event_type, created_at__gte=since)


def count_daily_to_monthly_upgrades(*, since=None, window_days: int = UPGRADE_WINDOW_DAYS) -> dict[str, Any]:
    """کاربرانی که پلن روزانه خریده‌اند و ظرف window_days به ماهانه ارتقا داده‌اند."""
    daily_qs = Order.objects.filter(
        status='paid',
        plan__plan_type='daily',
        paid_at__isnull=False,
    ).select_related('user', 'plan')
    if since is not None:
        daily_qs = daily_qs.filter(paid_at__gte=since)

    upgraded_users: set[int] = set()
    daily_buyers = 0
    window = timedelta(days=window_days)

    for daily_order in daily_qs.iterator():
        daily_buyers += 1
        upgraded = Order.objects.filter(
            user_id=daily_order.user_id,
            status='paid',
            plan__plan_type='monthly',
            paid_at__gt=daily_order.paid_at,
            paid_at__lte=daily_order.paid_at + window,
        ).exists()
        if upgraded:
            upgraded_users.add(daily_order.user_id)

    upgrade_count = len(upgraded_users)
    rate = round((upgrade_count / daily_buyers * 100), 1) if daily_buyers else 0.0
    return {
        'daily_buyers': daily_buyers,
        'upgrade_count': upgrade_count,
        'upgrade_rate': rate,
        'window_days': window_days,
    }


def _plan_purchases_in_period(since) -> dict[str, dict[str, int]]:
    rows = (
        _paid_orders_since(since)
        .values('plan__plan_type')
        .annotate(count=Count('id'), total=Sum('amount'))
    )
    result: dict[str, dict[str, int]] = {}
    for row in rows:
        plan_type = row['plan__plan_type'] or 'unknown'
        result[plan_type] = {
            'count': int(row['count'] or 0),
            'total': int(row['total'] or 0),
        }
    return result


def get_plan_conversion_by_plan(*, since, pricing_views: int, checkout_views: int) -> list[dict[str, Any]]:
    purchases = _plan_purchases_in_period(since)
    total_count = sum(item['count'] for item in purchases.values())
    total_revenue = sum(item['total'] for item in purchases.values())

    plans = (
        LicensePlan.objects.filter(is_active=True)
        .select_related('product')
        .order_by('order', 'price', 'id')
    )
    seen_types: set[tuple[int, str]] = set()
    rows: list[dict[str, Any]] = []

    for plan in plans:
        key = (plan.product_id, plan.plan_type or '')
        if key in seen_types:
            continue
        seen_types.add(key)

        stats = purchases.get(plan.plan_type or '', {'count': 0, 'total': 0})
        count = stats['count']
        total = stats['total']
        order_share = round((count / total_count * 100), 1) if total_count else 0.0
        revenue_share = round((total / total_revenue * 100), 1) if total_revenue else 0.0
        funnel_rate = round((count / pricing_views * 100), 2) if pricing_views else 0.0
        checkout_rate = round((count / checkout_views * 100), 2) if checkout_views else 0.0

        rows.append({
            'plan_type': plan.plan_type,
            'label': plan.name,
            'short_label': _plan_short_label(plan),
            'accent': PLAN_TYPE_ACCENTS.get(plan.plan_type, 'violet'),
            'price': int(plan.price or 0),
            'purchases': count,
            'revenue': total,
            'order_share': order_share,
            'revenue_share': revenue_share,
            'funnel_conversion': funnel_rate,
            'checkout_conversion': checkout_rate,
        })

    return rows


def get_weekly_purchase_series(*, since, weeks: int = 12) -> list[dict[str, Any]]:
    rows = (
        _paid_orders_since(since)
        .annotate(week=TruncWeek('paid_at'))
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
        series.append({
            'week': row['week'].date().isoformat(),
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
        Order.objects.filter(status='paid', paid_at__isnull=False)
        .values('user_id')
        .annotate(first_paid=Min('paid_at'))
        .order_by('-first_paid')[:5000]
    )

    cohorts: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'users': 0,
        'repeat_7d': 0,
        'repeat_30d': 0,
        'upgraded_monthly_7d': 0,
        'revenue': 0,
    })

    window_7 = timedelta(days=7)
    window_30 = timedelta(days=30)

    for row in first_paid_rows:
        user_id = row['user_id']
        first_paid = row['first_paid']
        week_start = first_paid.date() - timedelta(days=first_paid.weekday())
        key = week_start.isoformat()

        bucket = cohorts[key]
        bucket['users'] += 1

        user_orders = Order.objects.filter(user_id=user_id, status='paid', paid_at__isnull=False)
        user_revenue = user_orders.aggregate(total=Sum('amount'))['total'] or 0
        bucket['revenue'] += int(user_revenue)

        if user_orders.filter(
            paid_at__gt=first_paid,
            paid_at__lte=first_paid + window_7,
        ).exists():
            bucket['repeat_7d'] += 1

        if user_orders.filter(
            paid_at__gt=first_paid,
            paid_at__lte=first_paid + window_30,
        ).exists():
            bucket['repeat_30d'] += 1

        first_order = user_orders.order_by('paid_at').first()
        if first_order and first_order.plan and first_order.plan.plan_type == 'daily':
            if user_orders.filter(
                plan__plan_type='monthly',
                paid_at__gt=first_paid,
                paid_at__lte=first_paid + window_7,
            ).exists():
                bucket['upgraded_monthly_7d'] += 1

    result = []
    for week_key in sorted(cohorts.keys(), reverse=True)[:limit]:
        data = cohorts[week_key]
        users = data['users']
        result.append({
            'week': week_key,
            'users': users,
            'repeat_7d': data['repeat_7d'],
            'repeat_30d': data['repeat_30d'],
            'repeat_7d_rate': round((data['repeat_7d'] / users * 100), 1) if users else 0.0,
            'repeat_30d_rate': round((data['repeat_30d'] / users * 100), 1) if users else 0.0,
            'upgraded_monthly_7d': data['upgraded_monthly_7d'],
            'upgrade_rate': round((data['upgraded_monthly_7d'] / users * 100), 1) if users else 0.0,
            'avg_ltv': round(data['revenue'] / users) if users else 0,
        })
    return result


def get_funnel_daily_series(*, since) -> dict[str, list]:
    from django.db.models.functions import TruncDate

    pricing = (
        _funnel_events_since(since, 'pricing_view')
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    checkout = (
        _funnel_events_since(since, 'checkout_view')
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    purchases = (
        _paid_orders_since(since)
        .annotate(day=TruncDate('paid_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    return {
        'pricing_labels': [r['day'].isoformat() for r in pricing if r['day']],
        'pricing_counts': [r['count'] for r in pricing if r['day']],
        'checkout_labels': [r['day'].isoformat() for r in checkout if r['day']],
        'checkout_counts': [r['count'] for r in checkout if r['day']],
        'purchase_labels': [r['day'].isoformat() for r in purchases if r['day']],
        'purchase_counts': [r['count'] for r in purchases if r['day']],
    }


def build_plan_conversion_chart_payload(
    *,
    plan_rows: list[dict[str, Any]],
    weekly_series: list[dict[str, Any]],
    funnel_series: dict[str, list],
    plan_share_mode: str = 'revenue',
) -> dict[str, Any]:
    share_key = 'revenue_share' if plan_share_mode == 'revenue' else 'order_share'
    share_values = [row[share_key] for row in plan_rows]
    colors = [PLAN_CHART_COLORS[i % len(PLAN_CHART_COLORS)] for i in range(len(plan_rows))]

    return {
        'funnel_daily': funnel_series,
        'plan_share': {
            'labels': [row['short_label'] for row in plan_rows],
            'values': share_values,
            'revenue': [row['revenue'] for row in plan_rows],
            'purchases': [row['purchases'] for row in plan_rows],
            'colors': colors,
        },
        'plan_conversion': {
            'labels': [row['short_label'] for row in plan_rows],
            'funnel_rates': [row['funnel_conversion'] for row in plan_rows],
            'checkout_rates': [row['checkout_conversion'] for row in plan_rows],
            'accents': [row['accent'] for row in plan_rows],
        },
        'weekly_purchases': {
            'labels': [row['week'] for row in weekly_series],
            'total': [row['total'] for row in weekly_series],
            'daily': [row['daily'] for row in weekly_series],
            'monthly': [row['monthly'] for row in weekly_series],
            'revenue': [row['revenue'] for row in weekly_series],
        },
        'cohort_repeat': {
            'labels': [row['week'] for row in weekly_series[:8]],
        },
    }


def get_plan_conversion_context(*, days: int = 30) -> dict[str, Any]:
    days = _clamp_days(days)
    since = timezone.now() - timedelta(days=days)

    pricing_views = _funnel_events_since(since, 'pricing_view').count()
    pricing_unique = (
        _funnel_events_since(since, 'pricing_view')
        .values('session_key')
        .distinct()
        .count()
    )
    checkout_views = _funnel_events_since(since, 'checkout_view').count()
    upgrade_views = _funnel_events_since(since, 'upgrade_view').count()

    paid_qs = _paid_orders_since(since)
    paid_count = paid_qs.count()
    paid_revenue = int(paid_qs.aggregate(total=Sum('amount'))['total'] or 0)
    daily_purchases = paid_qs.filter(plan__plan_type='daily').count()

    upgrade_stats = count_daily_to_monthly_upgrades(since=since)

    overall_conversion = round((paid_count / pricing_views * 100), 2) if pricing_views else 0.0
    unique_conversion = round((paid_count / pricing_unique * 100), 2) if pricing_unique else 0.0
    checkout_conversion = round((paid_count / checkout_views * 100), 2) if checkout_views else 0.0

    plan_rows = get_plan_conversion_by_plan(
        since=since,
        pricing_views=pricing_views,
        checkout_views=checkout_views,
    )
    weekly_series = get_weekly_purchase_series(since=since)
    cohorts = get_purchase_cohorts(limit=12)
    funnel_series = get_funnel_daily_series(since=since)

    charts = build_plan_conversion_chart_payload(
        plan_rows=plan_rows,
        weekly_series=weekly_series,
        funnel_series=funnel_series,
    )
    charts['cohort'] = {
        'labels': [c['week'] for c in cohorts],
        'users': [c['users'] for c in cohorts],
        'repeat_7d_rate': [c['repeat_7d_rate'] for c in cohorts],
        'repeat_30d_rate': [c['repeat_30d_rate'] for c in cohorts],
        'upgrade_rate': [c['upgrade_rate'] for c in cohorts],
        'avg_ltv': [c['avg_ltv'] for c in cohorts],
    }

    plan_sales_all_time = get_plan_sales_breakdown()

    return {
        'days': days,
        'summary': {
            'pricing_views': pricing_views,
            'pricing_unique': pricing_unique,
            'checkout_views': checkout_views,
            'upgrade_views': upgrade_views,
            'paid_count': paid_count,
            'paid_revenue': paid_revenue,
            'daily_purchases': daily_purchases,
            'overall_conversion': overall_conversion,
            'unique_conversion': unique_conversion,
            'checkout_conversion': checkout_conversion,
            'upgrade_count': upgrade_stats['upgrade_count'],
            'upgrade_rate': upgrade_stats['upgrade_rate'],
            'daily_buyers_for_upgrade': upgrade_stats['daily_buyers'],
            'upgrade_window_days': upgrade_stats['window_days'],
        },
        'plan_rows': plan_rows,
        'weekly_series': weekly_series,
        'cohorts': cohorts,
        'plan_sales_all_time': plan_sales_all_time,
        'plan_type_labels': PLAN_TYPE_SHORT_LABELS,
        'charts': charts,
    }
