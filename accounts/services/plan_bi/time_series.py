"""تحلیل زمانی حرفه‌ای."""
from __future__ import annotations

from statistics import mean, pstdev
from typing import Any

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from accounts.services.plan_bi import (
    EMPTY_MSG,
    jalali_iso,
    jalali_week_label,
    paid_orders_qs,
    pct,
    to_local_date,
)


def _moving_avg(values: list[float], window: int = 3) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
            continue
        chunk = values[i + 1 - window: i + 1]
        out.append(round(mean(chunk), 2))
    return out


def build_time_intelligence(*, since, weekly_series: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if weekly_series is None:
        rows = (
            paid_orders_qs(since=since)
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
        weekly_series = []
        for row in rows:
            if not row['week']:
                continue
            week_dt = row['week']
            if timezone.is_aware(week_dt):
                week_dt = timezone.localtime(week_dt)
            week_date = to_local_date(week_dt)
            if not week_date:
                continue
            weekly_series.append({
                'week': week_date.isoformat(),
                'week_jalali': jalali_iso(week_date),
                'week_label': jalali_week_label(week_date),
                'total': int(row['total'] or 0),
                'daily': int(row['daily'] or 0),
                'monthly': int(row['monthly'] or 0),
                'quarterly': int(row['quarterly'] or 0),
                'yearly': int(row['yearly'] or 0),
                'revenue': int(row['revenue'] or 0),
            })

    if len(weekly_series) < 2:
        return {
            'available': False,
            'display': EMPTY_MSG,
            'series': weekly_series,
            'wow_growth': [],
            'moving_avg_orders': [],
            'moving_avg_revenue': [],
            'best_week': None,
            'worst_week': None,
            'top_revenue_week': None,
            'anomalies': [],
            'trend': 'unknown',
            'trend_label': EMPTY_MSG,
        }

    orders = [w['total'] for w in weekly_series]
    revenues = [w['revenue'] for w in weekly_series]
    wow = []
    for i in range(1, len(orders)):
        prev = orders[i - 1]
        cur = orders[i]
        wow.append({
            'week': weekly_series[i]['week_label'],
            'growth_pct': pct(cur - prev, prev, 1) if prev else (100.0 if cur else 0.0),
            'orders': cur,
            'revenue': revenues[i],
        })

    ma_orders = _moving_avg([float(x) for x in orders], 3)
    ma_revenue = _moving_avg([float(x) for x in revenues], 3)

    best = max(weekly_series, key=lambda w: w['total'])
    worst = min(weekly_series, key=lambda w: w['total'])
    top_rev = max(weekly_series, key=lambda w: w['revenue'])

    anomalies = []
    if len(orders) >= 4:
        mu = mean(orders)
        sd = pstdev(orders) or 1
        for w, o in zip(weekly_series, orders):
            z = (o - mu) / sd
            if abs(z) >= 1.8:
                anomalies.append({
                    'week': w['week_label'],
                    'week_jalali': w['week_jalali'],
                    'orders': o,
                    'z': round(z, 2),
                    'kind': 'spike' if z > 0 else 'drop',
                    'label': 'اوج غیرعادی' if z > 0 else 'افت غیرعادی',
                })

    # Trend: compare first half avg vs second half
    mid = len(orders) // 2
    first_avg = mean(orders[:mid]) if mid else 0
    second_avg = mean(orders[mid:]) if orders[mid:] else 0
    if second_avg > first_avg * 1.08:
        trend, trend_label = 'up', 'روند کلی صعودی'
    elif second_avg < first_avg * 0.92:
        trend, trend_label = 'down', 'روند کلی نزولی'
    else:
        trend, trend_label = 'flat', 'روند کلی ثابت'

    return {
        'available': True,
        'series': weekly_series,
        'wow_growth': wow,
        'moving_avg_orders': ma_orders,
        'moving_avg_revenue': ma_revenue,
        'best_week': {
            'label': best['week_label'],
            'jalali': best['week_jalali'],
            'orders': best['total'],
            'revenue': best['revenue'],
        },
        'worst_week': {
            'label': worst['week_label'],
            'jalali': worst['week_jalali'],
            'orders': worst['total'],
            'revenue': worst['revenue'],
        },
        'top_revenue_week': {
            'label': top_rev['week_label'],
            'jalali': top_rev['week_jalali'],
            'orders': top_rev['total'],
            'revenue': top_rev['revenue'],
        },
        'anomalies': anomalies,
        'trend': trend,
        'trend_label': trend_label,
    }
