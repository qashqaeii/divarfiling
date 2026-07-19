"""ابزارهای مشترک Plan BI."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import jdatetime
from django.db.models.functions import Coalesce
from django.utils import timezone

from shop.models import Order, PlanFunnelEvent
from workspace.services.jalali_input import PERSIAN_MONTHS, to_persian_digits

UPGRADE_WINDOW_DAYS = 7
EMPTY_MSG = 'داده کافی وجود ندارد'
IMMATURE_MSG = 'دوره مشاهده کامل نشده'
# حداقل نمونه برای همبستگی معنادار
MIN_SAMPLE = 3
CORR_MIN_GROUP = 10
CORR_MIN_TOTAL = 30
# سفارش pending قدیمی‌تر از این threshold (ساعت) می‌تواند stale باشد
PENDING_STALE_HOURS = 24
SCHEMA_VERSION = '2.3-abandon-preview'
# حداقل نمونه پس از tracking
POST_TRACKING_MIN_SAMPLE = 5
# زیر از این: Conversion قفل (insufficient)
POST_TRACKING_COVERAGE_LOCK_PCT = 50.0
# از این به بالا با نمونه کافی: Good / قابل اتکا
POST_TRACKING_COVERAGE_GOOD_PCT = 70.0
# سازگاری با importهای قدیمی
POST_TRACKING_COVERAGE_MIN_PCT = POST_TRACKING_COVERAGE_LOCK_PCT
# پیش‌فرض Job رها کردن Checkout (ساعت)
CHECKOUT_ABANDON_HOURS_DEFAULT = 2
CHECKOUT_ABANDON_BATCH_DEFAULT = 500



def clamp_days(days: int) -> int:
    return max(7, min(int(days), 365))


def pct(numerator: int | float, denominator: int | float, places: int = 2) -> float:
    if not denominator:
        return 0.0
    q = Decimal('0.1') ** places
    value = (Decimal(numerator) * Decimal(100) / Decimal(denominator)).quantize(
        q, rounding=ROUND_HALF_UP,
    )
    return float(value)


def conversion_rate(
    numerator: int | float,
    denominator: int | float,
    places: int = 2,
) -> float | None:
    """نرخ تبدیل معتبر؛ بالاتر از ۱۰۰٪ یا مخرج صفر → None."""
    if not denominator or numerator is None:
        return None
    if numerator < 0 or denominator < 0:
        return None
    if numerator > denominator:
        return None
    return pct(numerator, denominator, places)


def safe_div(numerator: int | float, denominator: int | float, places: int = 0) -> float | int:
    if not denominator:
        return 0 if places == 0 else 0.0
    if places == 0:
        return int(round(numerator / denominator))
    q = Decimal('0.1') ** places
    return float((Decimal(numerator) / Decimal(denominator)).quantize(q, rounding=ROUND_HALF_UP))


def to_local_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    if isinstance(value, date):
        return value
    return None


def jalali_iso(day: date) -> str:
    j = jdatetime.date.fromgregorian(date=day)
    return to_persian_digits(j.strftime('%Y/%m/%d'))


def jalali_day_label(day: date, *, compact: bool = False) -> str:
    j = jdatetime.date.fromgregorian(date=day)
    if compact:
        return to_persian_digits(f'{j.day:02d}/{j.month:02d}')
    month = PERSIAN_MONTHS[j.month - 1]
    return to_persian_digits(f'{j.day} {month}')


def jalali_week_label(week_start: date) -> str:
    j = jdatetime.date.fromgregorian(date=week_start)
    month = PERSIAN_MONTHS[j.month - 1]
    return to_persian_digits(f'هفته {j.day:02d} {month} {j.year}')


def week_start_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def paid_orders_qs(*, since=None, until=None):
    qs = (
        Order.objects.filter(status='paid')
        .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
        .select_related('plan', 'product', 'user')
    )
    if since is not None:
        qs = qs.filter(effective_paid__gte=since)
    if until is not None:
        qs = qs.filter(effective_paid__lt=until)
    return qs


def funnel_events_since(since, event_type: str | None = None):
    qs = PlanFunnelEvent.objects.filter(created_at__gte=since)
    if event_type:
        qs = qs.filter(event_type=event_type)
    return qs


def get_tracking_start() -> datetime | None:
    """اولین Event واقعی قیف خرید."""
    return (
        PlanFunnelEvent.objects.order_by('created_at')
        .values_list('created_at', flat=True)
        .first()
    )


def empty_metric(label: str = EMPTY_MSG) -> dict[str, Any]:
    return {
        'available': False,
        'label': label,
        'value': None,
        'display': label,
    }


def metric(value, *, display=None, available: bool = True) -> dict[str, Any]:
    return {
        'available': available,
        'value': value,
        'display': display if display is not None else value,
    }


def load_period_buyers(*, since, until=None) -> dict[str, Any]:
    """یک بار بارگذاری خریداران دوره برای reuse."""
    qs = paid_orders_qs(since=since, until=until).order_by('effective_paid')
    orders = list(qs)
    first_paid: dict[int, datetime] = {}
    revenue_by_user: dict[int, int] = {}
    plan_types_by_user: dict[int, list[str]] = {}
    order_count_by_user: dict[int, int] = {}

    for o in orders:
        uid = o.user_id
        ep = o.effective_paid
        revenue_by_user[uid] = revenue_by_user.get(uid, 0) + int(o.amount or 0)
        order_count_by_user[uid] = order_count_by_user.get(uid, 0) + 1
        plan_types_by_user.setdefault(uid, []).append(
            o.plan.plan_type if o.plan else '',
        )
        if uid not in first_paid and ep:
            first_paid[uid] = ep

    return {
        'orders': orders,
        'user_ids': list(first_paid.keys()),
        'first_paid': first_paid,
        'revenue_by_user': revenue_by_user,
        'plan_types_by_user': plan_types_by_user,
        'order_count_by_user': order_count_by_user,
        'paid_count': len(orders),
        'paid_revenue': sum(int(o.amount or 0) for o in orders),
        'unique_buyers': len(first_paid),
    }


def count_daily_to_monthly_upgrades(*, since=None, window_days: int = UPGRADE_WINDOW_DAYS) -> dict[str, Any]:
    daily_qs = (
        Order.objects.filter(status='paid', plan__plan_type='daily')
        .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
        .filter(effective_paid__isnull=False)
        .order_by('user_id', 'effective_paid')
    )
    if since is not None:
        daily_qs = daily_qs.filter(effective_paid__gte=since)

    first_daily: dict[int, datetime] = {}
    for order in daily_qs.iterator():
        if order.user_id not in first_daily:
            first_daily[order.user_id] = order.effective_paid

    upgraded: set[int] = set()
    upgrade_hours: list[float] = []
    window = timedelta(days=window_days)
    for user_id, first_paid in first_daily.items():
        monthly = (
            Order.objects.filter(user_id=user_id, status='paid', plan__plan_type='monthly')
            .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
            .filter(effective_paid__gt=first_paid, effective_paid__lte=first_paid + window)
            .order_by('effective_paid')
            .first()
        )
        if monthly:
            upgraded.add(user_id)
            delta = monthly.effective_paid - first_paid
            upgrade_hours.append(delta.total_seconds() / 3600)

    buyers = len(first_daily)
    count = len(upgraded)
    avg_hours = safe_div(sum(upgrade_hours), len(upgrade_hours), 1) if upgrade_hours else None
    return {
        'daily_buyers': buyers,
        'upgrade_count': count,
        'upgrade_rate': pct(count, buyers, 1) if buyers else None,
        'window_days': window_days,
        'avg_upgrade_hours': avg_hours,
        'available': buyers >= MIN_SAMPLE or count > 0,
    }


def period_bounds(days: int):
    days = clamp_days(days)
    now = timezone.now()
    since = now - timedelta(days=days)
    prev_since = since - timedelta(days=days)
    period_end = timezone.localdate()
    period_start = period_end - timedelta(days=days - 1)
    return {
        'days': days,
        'now': now,
        'since': since,
        'prev_since': prev_since,
        'prev_until': since,
        'period_start': period_start,
        'period_end': period_end,
    }


def delta_pct(current: float | int, previous: float | int) -> float | None:
    """درصد تغییر؛ اگر دوره قبل صفر باشد → None (نه ۱۰۰٪ جعلی)."""
    if previous in (0, None) and current in (0, None):
        return None
    if previous in (0, None):
        return None
    return pct(current - previous, previous, 1)


def comparison_status(current: float | int, previous: float | int) -> str:
    if previous in (0, None) and current not in (0, None) and current > 0:
        return 'new_activity'
    if previous in (0, None) and current in (0, None):
        return 'no_activity'
    d = delta_pct(current, previous)
    if d is None:
        return 'unknown'
    if d > 0:
        return 'up'
    if d < 0:
        return 'down'
    return 'flat'


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return round(ordered[f], 1)
    return round(ordered[f] + (ordered[c] - ordered[f]) * (k - f), 1)
