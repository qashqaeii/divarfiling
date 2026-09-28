"""DB-backed jobs for CRM property accessibility (POI) generation."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

JOB_STATUS_QUEUED = 'queued'
JOB_STATUS_RUNNING = 'running'
JOB_STATUS_DONE = 'done'
JOB_STATUS_FAILED = 'failed'
JOB_STATUS_CANCELLED = 'cancelled'

RETRIABLE_ERROR_CODES = frozenset({
    'service_busy',
    'service_unavailable',
    'global_limit',
})


def _pending_timeout_minutes() -> int:
    return int(getattr(settings, 'PROPERTY_ACCESSIBILITY_PENDING_TIMEOUT_MIN', 15))


def _job_max_attempts() -> int:
    return int(getattr(settings, 'PROPERTY_ACCESSIBILITY_JOB_MAX_ATTEMPTS', 3))


def _retry_backoff_seconds(attempt: int) -> int:
    base = int(getattr(settings, 'PROPERTY_ACCESSIBILITY_OVERPASS_RETRY_BACKOFF_S', 2))
    return base * max(1, attempt)


def enqueue_property_accessibility_job(
    property_id: int,
    user_id: Optional[int],
    generation_id: str,
) -> None:
    from workspace.models import PropertyAccessibilityJob

    now = timezone.now()
    PropertyAccessibilityJob.objects.filter(
        property_id=property_id,
        status__in=(JOB_STATUS_QUEUED, JOB_STATUS_RUNNING),
    ).exclude(
        generation_id=generation_id,
    ).update(
        status=JOB_STATUS_CANCELLED,
        finished_at=now,
        last_error='superseded by newer generation',
    )
    PropertyAccessibilityJob.objects.update_or_create(
        property_id=property_id,
        generation_id=generation_id,
        defaults={
            'user_id': user_id,
            'status': JOB_STATUS_QUEUED,
            'attempts': 0,
            'max_attempts': _job_max_attempts(),
            'run_after': now,
            'locked_at': None,
            'finished_at': None,
            'last_error': '',
        },
    )


def _pending_scheduled_at(prop):
    from workspace.services.nearby_pois import _parse_iso_datetime

    data = getattr(prop, 'nearby_pois', None) or {}
    return _parse_iso_datetime(data.get('scheduled_at'))


def is_property_accessibility_pending_stale(prop) -> bool:
    from workspace.services.nearby_pois import (
        ACCESSIBILITY_STATUS_PENDING,
        get_property_accessibility_status,
    )

    if get_property_accessibility_status(prop) != ACCESSIBILITY_STATUS_PENDING:
        return False
    scheduled_at = _pending_scheduled_at(prop)
    if not scheduled_at:
        return False
    return timezone.now() - scheduled_at >= timedelta(minutes=_pending_timeout_minutes())


def reconcile_stale_pending_accessibilities(*, timeout_minutes: Optional[int] = None) -> int:
    """Mark long-running pending states as failed so they can be retried."""
    from workspace.models import CRMProperty, PropertyAccessibilityJob
    from workspace.services.nearby_pois import (
        ACCESSIBILITY_STATUS_PENDING,
        mark_property_accessibilities_failed,
        resolve_property_location,
    )

    timeout = timeout_minutes if timeout_minutes is not None else _pending_timeout_minutes()
    cutoff = timezone.now() - timedelta(minutes=timeout)
    updated = 0

    stale_jobs = PropertyAccessibilityJob.objects.filter(
        status=JOB_STATUS_RUNNING,
        locked_at__lt=cutoff,
    )
    for job in stale_jobs.iterator():
        job.status = JOB_STATUS_FAILED
        job.finished_at = timezone.now()
        job.last_error = 'job timed out'
        job.save(update_fields=['status', 'finished_at', 'last_error', 'updated_at'])
        prop = job.property
        data = prop.nearby_pois or {}
        if data.get('generation_id') == job.generation_id:
            mark_property_accessibilities_failed(
                prop,
                error_code='stale_pending',
                error_message='محاسبه دسترسی‌ها بیش از حد طول کشید. دوباره «بروزرسانی» را بزنید.',
                generation_id=job.generation_id,
            )
        updated += 1

    for prop in CRMProperty.objects.exclude(nearby_pois={}).iterator():
        data = prop.nearby_pois or {}
        if data.get('status') != ACCESSIBILITY_STATUS_PENDING:
            continue
        scheduled_at = _pending_scheduled_at(prop)
        if not scheduled_at or scheduled_at > cutoff:
            continue
        generation_id = data.get('generation_id')
        has_active_job = PropertyAccessibilityJob.objects.filter(
            property_id=prop.pk,
            generation_id=generation_id,
            status__in=(JOB_STATUS_QUEUED, JOB_STATUS_RUNNING),
        ).exists()
        if has_active_job:
            continue
        mark_property_accessibilities_failed(
            prop,
            error_code='stale_pending',
            error_message='محاسبه دسترسی‌ها تکمیل نشد. دوباره «بروزرسانی» را بزنید.',
            generation_id=generation_id,
        )
        updated += 1
    return updated


def _process_single_job(job) -> None:
    from django.contrib.auth import get_user_model

    from workspace.services.nearby_pois import (
        NearbyPoiError,
        _generation_matches,
        refresh_property_accessibilities,
    )

    User = get_user_model()
    prop = job.property
    if not _generation_matches(prop, job.generation_id):
        job.status = JOB_STATUS_CANCELLED
        job.finished_at = timezone.now()
        job.last_error = 'generation superseded'
        job.save(update_fields=['status', 'finished_at', 'last_error', 'updated_at'])
        return

    user = None
    if job.user_id:
        user = User.objects.filter(pk=job.user_id).first()
    if not user:
        user = prop.user

    try:
        refresh_property_accessibilities(
            prop,
            user,
            force_refresh=True,
            generation_id=job.generation_id,
        )
        job.status = JOB_STATUS_DONE
        job.finished_at = timezone.now()
        job.last_error = ''
        job.save(update_fields=['status', 'finished_at', 'last_error', 'updated_at'])
    except NearbyPoiError as exc:
        job.last_error = (exc.message or exc.code or '')[:500]
        if exc.code in RETRIABLE_ERROR_CODES and job.attempts < job.max_attempts:
            job.status = JOB_STATUS_QUEUED
            job.run_after = timezone.now() + timedelta(seconds=_retry_backoff_seconds(job.attempts))
            job.finished_at = None
            job.save(update_fields=['status', 'run_after', 'finished_at', 'last_error', 'updated_at'])
            return
        job.status = JOB_STATUS_FAILED
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'finished_at', 'last_error', 'updated_at'])


def _claim_queued_jobs(queryset, *, limit: int) -> list:
    now = timezone.now()
    with transaction.atomic():
        jobs = list(
            queryset.select_for_update(skip_locked=True)
            .filter(status=JOB_STATUS_QUEUED, run_after__lte=now)
            .order_by('run_after', 'id')[:limit],
        )
        for job in jobs:
            job.status = JOB_STATUS_RUNNING
            job.attempts += 1
            job.locked_at = now
            job.save(update_fields=['status', 'attempts', 'locked_at', 'updated_at'])
    return jobs


def _run_claimed_jobs(jobs) -> int:
    processed = 0
    for job in jobs:
        try:
            _process_single_job(job)
            processed += 1
        except Exception:
            logger.exception('property accessibility job crashed job=%s', job.pk)
            job.status = JOB_STATUS_FAILED
            job.finished_at = timezone.now()
            job.last_error = 'unexpected worker error'
            job.save(update_fields=['status', 'finished_at', 'last_error', 'updated_at'])
        finally:
            close_old_connections()
    return processed


def process_property_accessibility_jobs_for_property(
    property_id: int,
    *,
    limit: int = 2,
) -> int:
    """Run queued jobs for one property (inline fallback when no cron worker)."""
    from workspace.models import PropertyAccessibilityJob

    close_old_connections()
    jobs = _claim_queued_jobs(
        PropertyAccessibilityJob.objects.filter(property_id=property_id),
        limit=limit,
    )
    return _run_claimed_jobs(jobs)


def process_property_accessibility_jobs(*, limit: int = 10) -> int:
    """Claim and run queued accessibility jobs. Safe for cron/worker loops."""
    from workspace.models import PropertyAccessibilityJob

    close_old_connections()
    reconcile_stale_pending_accessibilities()
    jobs = _claim_queued_jobs(PropertyAccessibilityJob.objects.all(), limit=limit)
    return _run_claimed_jobs(jobs)
