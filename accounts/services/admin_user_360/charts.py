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


USAGE_CHART_LABELS = {
    'ربات ویندوز': 'نرم‌افزار ویندوز',
    'اپ اندروید': 'اپلیکیشن اندروید',
    'استخراج آگهی': 'استخراج از دیوار',
    'دیتاست‌ها': 'فایل‌های دیتاست',
    'آگهی در بانک فایل': 'آگهی در بانک فایل',
    'شمارش آگهی‌ها': 'آگهی در بانک فایل',
    'مخاطبین': 'مخاطبین CRM',
    'معاملات': 'معاملات CRM',
    'یادآورها': 'یادآورها',
    'کار روی آگهی فایل': 'کار روی آگهی‌های فایل',
    'فعالیت لیستینگ دیوار': 'کار روی آگهی‌های فایل',
    'همگام‌سازی موبایل': 'همگام‌سازی موبایل',
}

# حجم ذخیره‌شده (مثل تعداد کل آگهی) با «تعداد استفاده» قابل مقایسه در نمودار نیست.
USAGE_CHART_EXCLUDE_NAMES = frozenset({
    'شمارش آگهی‌ها',
    'آگهی در بانک فایل',
})


def chart_feature_usage(features: List[Dict[str, Any]], *, limit: int = 8) -> List[Dict[str, Any]]:
    ranked = []
    for f in features or []:
        name = (f.get('name') or '').strip()
        if not name or name in USAGE_CHART_EXCLUDE_NAMES:
            continue
        count = int(f.get('count') or 0)
        if count <= 0:
            continue
        ranked.append({
            'label': USAGE_CHART_LABELS.get(name, name),
            'count': count,
        })
    ranked.sort(key=lambda item: item['count'], reverse=True)
    return ranked[:limit]


def chart_ticket_status(user) -> List[Dict[str, Any]]:
    from workspace.models import Ticket
    from workspace.support_constants import TICKET_STATUS_CHOICES

    rows = Ticket.objects.filter(user=user).values('status').annotate(count=Count('id')).order_by('-count')
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


def chart_audit_action_counts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """توزیع نوع عملیات لاگ لایسنس."""
    out = []
    for row in rows or []:
        label = row.get('label') or row.get('key') or '—'
        count = int(row.get('count') or 0)
        if count > 0:
            out.append({'label': label, 'count': count, 'key': row.get('key', '')})
    return out


def chart_audit_log_daily(qs, *, span_days: int = 14) -> List[Dict[str, Any]]:
    """شمارش روزانه لاگ لایسنس برای نمودار."""
    from django.db.models import Count
    from django.db.models.functions import TruncDate

    from accounts.services.admin_user_360.common import fa_digits

    span_days = max(3, min(int(span_days or 14), 60))
    since = timezone.now() - timedelta(days=span_days)
    rows = (
        qs.filter(created_at__gte=since)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    buckets: Dict[str, int] = {}
    for row in rows:
        day = row.get('day')
        if not day:
            continue
        buckets[day.isoformat()] = int(row['count'] or 0)
    anchor = timezone.localtime(timezone.now()).date()
    out: List[Dict[str, Any]] = []
    for offset in range(span_days - 1, -1, -1):
        d = anchor - timedelta(days=offset)
        key = d.isoformat()
        j = jdatetime.date.fromgregorian(date=d)
        label = f'{fa_digits(j.day)}/{fa_digits(j.month)}'
        out.append({'date': key, 'label': label, 'count': buckets.get(key, 0)})
    return out


def chart_crm_status_breakdown(breakdown: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for item in breakdown or []:
        label = item.get('label') or item.get('status') or '—'
        count = int(item.get('count') or item.get('total') or 0)
        if count:
            out.append({'label': label, 'count': count})
    return out
