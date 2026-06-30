"""سرویس زمان‌بندی استخراج سبک موبایل."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import models, transaction
from django.utils import timezone

from mobile_api.models import MobileExtractionRun, MobileExtractionSchedule
from mobile_api.services.extraction_ingest import (
    EXTRACTIONS_DAILY_LIMIT,
    check_mobile_extraction_allowed,
    mobile_extractions_today_count,
)

logger = logging.getLogger(__name__)

MIN_INTERVAL_HOURS = 0.25
MAX_INTERVAL_HOURS = 168.0
MAX_SCHEDULES_PER_USER = 10
MAX_CONSECUTIVE_FAILURES = 5
STALE_RUN_TIMEOUT = timedelta(minutes=15)


def _clamp_interval(hours: float) -> float:
    try:
        value = float(hours)
    except (TypeError, ValueError):
        value = 6.0
    return max(MIN_INTERVAL_HOURS, min(MAX_INTERVAL_HOURS, value))


def schedule_title_from_filters(filters: Dict[str, Any]) -> str:
    parts = [
        str(filters.get('city_name') or '').strip(),
        str(filters.get('transaction_type_label') or '').strip(),
        str(filters.get('category_label') or '').strip(),
    ]
    search_query = str(filters.get('search_query') or '').strip()
    if search_query:
        parts.append(f'«{search_query[:40]}»')
    parts = [p for p in parts if p]
    if parts:
        return ' — '.join(parts)[:200]
    category = str(filters.get('category') or '').strip()
    return category[:200] if category else 'استخراج زمان‌بندی‌شده'


def compute_next_run_at(schedule: MobileExtractionSchedule, *, from_time=None):
    base = from_time or timezone.now()
    return base + timedelta(hours=_clamp_interval(schedule.interval_hours))


def _validate_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(filters, dict):
        raise ValueError('فیلترها نامعتبر است.')
    category = str(filters.get('category') or '').strip()
    city_id = str(filters.get('city_id') or '').strip()
    if not category:
        raise ValueError('دسته‌بندی آگهی الزامی است.')
    if not city_id:
        raise ValueError('شهر الزامی است.')
    return filters


def get_schedule(user, schedule_id: int) -> Optional[MobileExtractionSchedule]:
    return MobileExtractionSchedule.objects.filter(user=user, pk=schedule_id).first()


def list_schedules(user) -> List[MobileExtractionSchedule]:
    return list(MobileExtractionSchedule.objects.filter(user=user).order_by('-updated_at'))


def create_schedule(user, data: Dict[str, Any], *, device_id: str = '') -> MobileExtractionSchedule:
    count = MobileExtractionSchedule.objects.filter(user=user).count()
    if count >= MAX_SCHEDULES_PER_USER:
        raise ValueError(f'حداکثر {MAX_SCHEDULES_PER_USER} زمان‌بندی مجاز است.')

    filters = _validate_filters(data.get('filters') or {})
    interval = _clamp_interval(data.get('interval_hours', 6))
    max_items = int(data.get('max_items') or filters.get('max_items') or 50)
    max_items = max(1, min(100, max_items))
    filters['max_items'] = max_items

    title = (data.get('title') or '').strip() or schedule_title_from_filters(filters)
    is_enabled = bool(data.get('is_enabled', True))
    now = timezone.now()

    schedule = MobileExtractionSchedule(
        user=user,
        title=title[:200],
        is_enabled=is_enabled,
        interval_hours=interval,
        filters=filters,
        max_items=max_items,
        primary_device_id=(device_id or data.get('device_id') or '')[:128],
        next_run_at=now if is_enabled else None,
        last_status=MobileExtractionSchedule.RUN_STATUS_IDLE,
    )
    if is_enabled:
        schedule.next_run_at = now
    schedule.save()
    return schedule


def update_schedule(user, schedule_id: int, data: Dict[str, Any]) -> Optional[MobileExtractionSchedule]:
    schedule = get_schedule(user, schedule_id)
    if not schedule:
        return None

    if 'title' in data and data['title']:
        schedule.title = str(data['title']).strip()[:200]
    if 'filters' in data and data['filters']:
        schedule.filters = _validate_filters(data['filters'])
        if not (data.get('title') or '').strip():
            schedule.title = schedule_title_from_filters(schedule.filters)
    if 'interval_hours' in data:
        schedule.interval_hours = _clamp_interval(data['interval_hours'])
    if 'max_items' in data:
        schedule.max_items = max(1, min(100, int(data['max_items'] or 50)))
        schedule.filters = {**(schedule.filters or {}), 'max_items': schedule.max_items}
    if 'is_enabled' in data:
        enabled = bool(data['is_enabled'])
        if enabled and not schedule.is_enabled:
            schedule.next_run_at = timezone.now()
            schedule.consecutive_failures = 0
        elif not enabled:
            schedule.next_run_at = None
        schedule.is_enabled = enabled
    if 'device_id' in data:
        schedule.primary_device_id = str(data['device_id'] or '')[:128]

    schedule.save()
    return schedule


def delete_schedule(user, schedule_id: int) -> bool:
    deleted, _ = MobileExtractionSchedule.objects.filter(user=user, pk=schedule_id).delete()
    return deleted > 0


def toggle_schedule(user, schedule_id: int, *, enabled: Optional[bool] = None) -> Optional[MobileExtractionSchedule]:
    schedule = get_schedule(user, schedule_id)
    if not schedule:
        return None
    schedule.is_enabled = not schedule.is_enabled if enabled is None else bool(enabled)
    if schedule.is_enabled:
        schedule.next_run_at = timezone.now()
        schedule.consecutive_failures = 0
    else:
        schedule.next_run_at = None
    schedule.save()
    return schedule


def list_runs(user, schedule_id: int, *, page: int = 1, page_size: int = 20) -> Tuple[List[MobileExtractionRun], dict]:
    from django.core.paginator import Paginator

    schedule = get_schedule(user, schedule_id)
    if not schedule:
        return [], {'page': page, 'page_size': page_size, 'total': 0}
    qs = MobileExtractionRun.objects.filter(schedule=schedule).order_by('-started_at')
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    meta = {'page': page, 'page_size': page_size, 'total': paginator.count}
    return list(page_obj.object_list), meta


def _has_active_run(schedule: MobileExtractionSchedule) -> bool:
    return MobileExtractionRun.objects.filter(
        schedule=schedule,
        status=MobileExtractionSchedule.RUN_STATUS_RUNNING,
    ).exists()


def _expire_stale_runs(schedule: MobileExtractionSchedule) -> int:
    """اجراهای گیرکرده (مثلاً بعد از کرش اپ) را می‌بندد."""
    cutoff = timezone.now() - STALE_RUN_TIMEOUT
    stale = MobileExtractionRun.objects.filter(
        schedule=schedule,
        status=MobileExtractionSchedule.RUN_STATUS_RUNNING,
        started_at__lt=cutoff,
    )
    count = stale.count()
    if not count:
        return 0
    now = timezone.now()
    stale.update(
        status=MobileExtractionSchedule.RUN_STATUS_FAILED,
        error='اجرای قبلی به‌صورت خودکار بسته شد (timeout).',
        finished_at=now,
    )
    schedule.refresh_from_db()
    if schedule.last_status == MobileExtractionSchedule.RUN_STATUS_RUNNING:
        schedule.last_status = MobileExtractionSchedule.RUN_STATUS_FAILED
        schedule.last_error = 'اجرای قبلی منقضی شد.'
        schedule.next_run_at = compute_next_run_at(schedule, from_time=now)
        schedule.save(update_fields=['last_status', 'last_error', 'next_run_at', 'updated_at'])
    logger.info('Expired %s stale extraction run(s) for schedule=%s', count, schedule.pk)
    return count


def start_schedule_run(
    user,
    schedule_id: int,
    *,
    trigger: str = MobileExtractionRun.TRIGGER_DEVICE,
    device_id: str = '',
) -> MobileExtractionRun:
    schedule = get_schedule(user, schedule_id)
    if not schedule:
        raise ValueError('زمان‌بندی یافت نشد.')
    if not schedule.is_enabled:
        raise ValueError('زمان‌بندی غیرفعال است.')
    _expire_stale_runs(schedule)
    if _has_active_run(schedule):
        raise ValueError('اجرای قبلی هنوز تمام نشده است.')
    if schedule.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        raise ValueError('زمان‌بندی به‌دلیل خطاهای متوالی متوقف شده — دوباره فعال کنید.')

    try:
        check_mobile_extraction_allowed(user)
    except ValueError as exc:
        run = MobileExtractionRun.objects.create(
            user=user,
            schedule=schedule,
            status=MobileExtractionSchedule.RUN_STATUS_SKIPPED_LIMIT,
            trigger=trigger,
            filters_snapshot=schedule.filters or {},
            error=str(exc),
            finished_at=timezone.now(),
        )
        schedule.last_status = MobileExtractionSchedule.RUN_STATUS_SKIPPED_LIMIT
        schedule.last_error = str(exc)
        schedule.last_run_at = timezone.now()
        schedule.next_run_at = compute_next_run_at(schedule)
        schedule.save(update_fields=[
            'last_status', 'last_error', 'last_run_at', 'next_run_at', 'updated_at',
        ])
        raise

    filters = dict(schedule.filters or {})
    filters['max_items'] = schedule.max_items
    filters['source_client'] = filters.get('source_client') or 'android_schedule'

    run = MobileExtractionRun.objects.create(
        user=user,
        schedule=schedule,
        status=MobileExtractionSchedule.RUN_STATUS_RUNNING,
        trigger=trigger,
        filters_snapshot=filters,
    )
    schedule.last_status = MobileExtractionSchedule.RUN_STATUS_RUNNING
    schedule.last_error = ''
    if device_id:
        schedule.primary_device_id = device_id[:128]
    schedule.save(update_fields=['last_status', 'last_error', 'primary_device_id', 'updated_at'])
    return run


def complete_schedule_run(
    user,
    run_id: int,
    *,
    dataset_id: str,
    ingested_count: int,
    created_count: int = 0,
    updated_count: int = 0,
    skipped_count: int = 0,
) -> Optional[MobileExtractionRun]:
    run = MobileExtractionRun.objects.filter(user=user, pk=run_id).select_related('schedule').first()
    if not run:
        return None
    if run.status != MobileExtractionSchedule.RUN_STATUS_RUNNING or run.finished_at is not None:
        return None
    now = timezone.now()
    run.status = MobileExtractionSchedule.RUN_STATUS_SUCCESS
    run.dataset_id = dataset_id or None
    run.ingested_count = ingested_count
    run.created_count = created_count
    run.updated_count = updated_count
    run.skipped_count = skipped_count
    run.finished_at = now
    run.save()

    schedule = run.schedule
    if schedule:
        schedule.last_status = MobileExtractionSchedule.RUN_STATUS_SUCCESS
        schedule.last_error = ''
        schedule.last_run_at = now
        schedule.last_dataset_id = dataset_id or None
        schedule.run_count += 1
        schedule.consecutive_failures = 0
        schedule.next_run_at = compute_next_run_at(schedule, from_time=now)
        schedule.save(update_fields=[
            'last_status', 'last_error', 'last_run_at', 'last_dataset_id',
            'run_count', 'consecutive_failures', 'next_run_at', 'updated_at',
        ])
    return run


def fail_schedule_run(user, run_id: int, error: str) -> Optional[MobileExtractionRun]:
    run = MobileExtractionRun.objects.filter(user=user, pk=run_id).select_related('schedule').first()
    if not run:
        return None
    now = timezone.now()
    run.status = MobileExtractionSchedule.RUN_STATUS_FAILED
    run.error = (error or 'خطای نامشخص')[:2000]
    run.finished_at = now
    run.save()

    schedule = run.schedule
    if schedule:
        schedule.last_status = MobileExtractionSchedule.RUN_STATUS_FAILED
        schedule.last_error = run.error
        schedule.last_run_at = now
        schedule.consecutive_failures += 1
        schedule.next_run_at = compute_next_run_at(schedule, from_time=now)
        if schedule.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            schedule.is_enabled = False
            schedule.next_run_at = None
        schedule.save(update_fields=[
            'last_status', 'last_error', 'last_run_at', 'consecutive_failures',
            'is_enabled', 'next_run_at', 'updated_at',
        ])
    return run


def list_due_schedules(user, *, device_id: str = '') -> List[MobileExtractionSchedule]:
    now = timezone.now()
    qs = MobileExtractionSchedule.objects.filter(
        user=user,
        is_enabled=True,
        next_run_at__lte=now,
    ).exclude(
        last_status=MobileExtractionSchedule.RUN_STATUS_RUNNING,
    )
    if device_id:
        qs = qs.filter(
            models.Q(primary_device_id='') | models.Q(primary_device_id=device_id)
        )
    return list(qs.order_by('next_run_at')[:5])


def list_due_schedules_global(limit: int = 50) -> List[MobileExtractionSchedule]:
    now = timezone.now()
    return list(
        MobileExtractionSchedule.objects.filter(
            is_enabled=True,
            next_run_at__lte=now,
        ).exclude(
            last_status=MobileExtractionSchedule.RUN_STATUS_RUNNING,
        ).select_related('user').order_by('next_run_at')[:limit]
    )
