"""تقویم پاک‌سازی ماهانه و محاسبه scheduled_deletion_at."""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from workspace.constants import (
    FILING_LISTING_RETENTION_DAYS_DEFAULT,
    FILING_RETENTION_CLEANUP_DAY_DEFAULT,
    FILING_RETENTION_CLEANUP_HOUR_DEFAULT,
    FILING_RETENTION_WARNING_DAYS_DEFAULT,
    WORKFLOW_RETENTION_TAGS,
)


def filing_listing_retention_days() -> int:
    raw = getattr(settings, 'FILING_LISTING_RETENTION_DAYS', FILING_LISTING_RETENTION_DAYS_DEFAULT)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = FILING_LISTING_RETENTION_DAYS_DEFAULT
    return max(1, min(3650, days))


def filing_retention_warning_days() -> int:
    raw = getattr(settings, 'FILING_RETENTION_WARNING_DAYS', FILING_RETENTION_WARNING_DAYS_DEFAULT)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return FILING_RETENTION_WARNING_DAYS_DEFAULT


def filing_retention_cleanup_day() -> int:
    raw = getattr(settings, 'FILING_RETENTION_CLEANUP_DAY', FILING_RETENTION_CLEANUP_DAY_DEFAULT)
    try:
        return max(1, min(28, int(raw)))
    except (TypeError, ValueError):
        return FILING_RETENTION_CLEANUP_DAY_DEFAULT


def filing_retention_cleanup_hour() -> int:
    raw = getattr(settings, 'FILING_RETENTION_CLEANUP_HOUR', FILING_RETENTION_CLEANUP_HOUR_DEFAULT)
    try:
        return max(0, min(23, int(raw)))
    except (TypeError, ValueError):
        return FILING_RETENTION_CLEANUP_HOUR_DEFAULT


def retention_feature_deployed_at():
    raw = getattr(settings, 'RETENTION_WARNING_FEATURE_DEPLOYED_AT', None)
    if not raw:
        return None
    if hasattr(raw, 'tzinfo'):
        return raw if timezone.is_aware(raw) else timezone.make_aware(raw)
    from django.utils.dateparse import parse_datetime
    parsed = parse_datetime(str(raw))
    if parsed and timezone.is_aware(parsed):
        return parsed
    if parsed:
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return None


def monthly_cleanup_datetime(year: int, month: int, *, as_of=None) -> timezone.datetime:
    cleanup_day = filing_retention_cleanup_day()
    hour = filing_retention_cleanup_hour()
    last_dom = calendar.monthrange(year, month)[1]
    day = min(cleanup_day, last_dom)
    tz = timezone.get_current_timezone()
    naive = datetime(year, month, day, hour, 0, 0)
    return timezone.make_aware(naive, tz)


def first_cleanup_on_or_after(dt: timezone.datetime) -> timezone.datetime:
    local = timezone.localtime(dt)
    candidate = monthly_cleanup_datetime(local.year, local.month)
    if candidate >= dt:
        return candidate
    month = local.month + 1
    year = local.year
    if month > 12:
        month = 1
        year += 1
    return monthly_cleanup_datetime(year, month)


def current_month_cleanup_datetime(as_of=None) -> timezone.datetime:
    as_of = as_of or timezone.now()
    local = timezone.localtime(as_of)
    return monthly_cleanup_datetime(local.year, local.month, as_of=as_of)


def next_monthly_cleanup_datetime(as_of=None) -> timezone.datetime:
    as_of = as_of or timezone.now()
    local = timezone.localtime(as_of)
    cleanup = monthly_cleanup_datetime(local.year, local.month)
    if cleanup > as_of:
        return cleanup
    month = local.month + 1
    year = local.year
    if month > 12:
        month = 1
        year += 1
    return monthly_cleanup_datetime(year, month)


def is_monthly_cleanup_day(as_of=None) -> bool:
    as_of = as_of or timezone.now()
    local = timezone.localtime(as_of)
    return local.day == filing_retention_cleanup_day()


def scheduled_deletion_at(
    effective_last_activity_at: timezone.datetime,
    *,
    retention_days: int,
    as_of=None,
) -> timezone.datetime | None:
    """اولین پاک‌سازی ماهانه بعد از تکمیل دوره inactivity."""
    as_of = as_of or timezone.now()
    if not effective_last_activity_at:
        return None
    inactive_threshold = effective_last_activity_at + timedelta(days=retention_days)
    if as_of < inactive_threshold:
        return None
    return first_cleanup_on_or_after(inactive_threshold)


def warning_window_start(scheduled: timezone.datetime) -> timezone.datetime:
    return scheduled - timedelta(days=filing_retention_warning_days())


def days_until_deletion(scheduled: timezone.datetime, as_of=None) -> int:
    as_of = as_of or timezone.now()
    local_as_of = timezone.localtime(as_of).date()
    local_sched = timezone.localtime(scheduled).date()
    return max(0, (local_sched - local_as_of).days)


def is_rollout_safe_for_purge(
    scheduled: timezone.datetime | None,
    *,
    as_of=None,
) -> bool:
    """اولین cleanup بعد از deploy — grace سه‌روزه اجباری."""
    deployed_at = retention_feature_deployed_at()
    if not deployed_at or not scheduled:
        return True
    warning_start = warning_window_start(scheduled)
    return warning_start >= deployed_at
