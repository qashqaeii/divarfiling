"""داده نمودارهای پرونده ۳۶۰ — فقط از رویداد/مدل واقعی."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List

import jdatetime
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.services.admin_users_management import ORDER_STATUS_LABELS
from shop.models import Order

_JALALI_MONTHS_FA = (
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
)


def _month_start_prev(dt):
    month = dt.month - 1
    year = dt.year
    if month < 1:
        month = 12
        year -= 1
    return dt.replace(year=year, month=month, day=1)


def chart_orders_by_status(user) -> List[Dict[str, Any]]:
    rows = (
        Order.objects.filter(user=user)
        .values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    return [
        {
            'key': row['status'],
            'label': ORDER_STATUS_LABELS.get(row['status'], row['status']),
            'count': int(row['count']),
        }
        for row in rows
        if row['count']
    ]


def chart_paid_revenue_monthly(user, *, months: int = 6) -> List[Dict[str, Any]]:
    since = timezone.now() - timedelta(days=months * 31)
    qs = (
        Order.objects.filter(user=user, status='paid', paid_at__gte=since)
        .annotate(month=TruncMonth('paid_at'))
        .values('month')
        .annotate(total=Sum('amount'), orders=Count('id'))
        .order_by('month')
    )
    by_month: Dict[str, Dict[str, int]] = {}
    for row in qs:
        if not row['month']:
            continue
        key = row['month'].strftime('%Y-%m')
        by_month[key] = {
            'total': int(row['total'] or 0),
            'orders': int(row['orders'] or 0),
        }

    anchor = timezone.localtime(timezone.now()).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0,
    )
    month_starts = []
    cur = anchor
    for _ in range(months):
        month_starts.insert(0, cur)
        cur = _month_start_prev(cur)

    from accounts.services.admin_user_360.common import fa_digits

    out: List[Dict[str, Any]] = []
    for m_start in month_starts:
        key = m_start.strftime('%Y-%m')
        bucket = by_month.get(key, {})
        j = jdatetime.date.fromgregorian(date=m_start.date())
        label = _JALALI_MONTHS_FA[j.month - 1]
        if months > 1:
            label = f'{label} {fa_digits(j.year)}'
        out.append({
            'month': key,
            'label': label,
            'total': int(bucket.get('total') or 0),
            'orders': int(bucket.get('orders') or 0),
        })
    return out


def chart_license_status_counts(license_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, int] = defaultdict(int)
    for row in license_rows:
        label = row.get('status_label') or row.get('status') or '—'
        buckets[label] += 1
    return [{'label': k, 'count': v} for k, v in sorted(buckets.items(), key=lambda x: -x[1])]


def chart_feature_usage(features: List[Dict[str, Any]], *, limit: int = 10) -> List[Dict[str, Any]]:
    ranked = [f for f in features if int(f.get('count') or 0) > 0]
    ranked.sort(key=lambda f: int(f.get('count') or 0), reverse=True)
    return [{'label': f['name'], 'count': int(f['count'])} for f in ranked[:limit]]


def chart_ticket_status(user) -> List[Dict[str, Any]]:
    from workspace.models import Ticket

    rows = Ticket.objects.filter(user=user).values('status').annotate(count=Count('id')).order_by('-count')
    from workspace.models import TICKET_STATUS_CHOICES

    status_labels = dict(TICKET_STATUS_CHOICES)
    return [
        {
            'key': row['status'],
            'label': status_labels.get(row['status'], row['status']),
            'count': int(row['count']),
        }
        for row in rows
        if row['count']
    ]


def chart_crm_status_breakdown(breakdown: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for item in breakdown or []:
        label = item.get('label') or item.get('status') or '—'
        count = int(item.get('count') or item.get('total') or 0)
        if count:
            out.append({'label': label, 'count': count})
    return out
