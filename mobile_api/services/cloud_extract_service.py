"""استخراج ابری دیوار — اجرای پس‌زمینه روی سرور."""
from __future__ import annotations

import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.db import close_old_connections
from django.utils import timezone

from mobile_api.models import MobileCloudExtractionJob
from mobile_api.services.extraction_ingest import check_mobile_extraction_allowed, ingest_mobile_extraction

logger = logging.getLogger(__name__)

MAX_CLOUD_ITEMS = 500
MAX_CONCURRENT_CLOUD_JOBS = 2
DETAIL_WORKERS = 2

_JOB_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_CLOUD_JOBS)
_SCRAPER_DIR = Path(__file__).resolve().parents[2] / 'scraper'


def job_to_dict(job: MobileCloudExtractionJob) -> Dict[str, Any]:
    return {
        'id': job.pk,
        'status': job.status,
        'filters': job.filters or {},
        'max_items': job.max_items,
        'dataset_id': str(job.dataset_id) if job.dataset_id else None,
        'ingested_count': job.ingested_count,
        'error': job.error or '',
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'finished_at': job.finished_at.isoformat() if job.finished_at else None,
    }


def list_jobs(user) -> List[MobileCloudExtractionJob]:
    return list(
        MobileCloudExtractionJob.objects.filter(user=user).order_by('-created_at')[:50]
    )


def get_job(user, job_id: int) -> Optional[MobileCloudExtractionJob]:
    return MobileCloudExtractionJob.objects.filter(user=user, pk=job_id).first()


def _validate_create_data(data: Dict[str, Any]) -> tuple[Dict[str, Any], int]:
    filters = data.get('filters') or data
    if not isinstance(filters, dict):
        raise ValueError('فیلترها نامعتبر است.')
    category = str(filters.get('category') or data.get('category') or '').strip()
    city_id = str(filters.get('city_id') or data.get('city_id') or '').strip()
    if not category:
        raise ValueError('دسته‌بندی آگهی الزامی است.')
    if not city_id:
        raise ValueError('شهر الزامی است.')

    try:
        max_items = int(data.get('max_items') or filters.get('max_items') or 200)
    except (TypeError, ValueError):
        raise ValueError('حداکثر تعداد آگهی نامعتبر است.') from None
    max_items = max(1, min(MAX_CLOUD_ITEMS, max_items))
    filters = dict(filters)
    filters['category'] = category
    filters['city_id'] = city_id
    filters['max_items'] = max_items
    filters['source_client'] = 'cloud_extract'
    return filters, max_items


def create_job(user, data: Dict[str, Any]) -> MobileCloudExtractionJob:
    filters, max_items = _validate_create_data(data)
    job = MobileCloudExtractionJob.objects.create(
        user=user,
        status=MobileCloudExtractionJob.STATUS_QUEUED,
        filters=filters,
        max_items=max_items,
    )
    thread = threading.Thread(target=run_job, args=(job.pk,), daemon=True)
    thread.start()
    return job


def _ensure_scraper_import():
    scraper_path = str(_SCRAPER_DIR)
    if _SCRAPER_DIR.exists() and scraper_path not in sys.path:
        sys.path.insert(0, scraper_path)
    from export_divar_items import (  # noqa: WPS433
        CONFIG,
        fetch_post_detail,
        fetch_post_tokens,
        get_http_session,
    )
    return CONFIG, fetch_post_tokens, fetch_post_detail, get_http_session


def _configure_scraper(CONFIG, filters: Dict[str, Any], max_items: int) -> None:
    city_id = str(filters.get('city_id') or '').strip()
    district_ids = filters.get('district_ids') or []
    if not isinstance(district_ids, list):
        district_ids = [str(district_ids)] if district_ids else []
    district_ids = [str(d).strip() for d in district_ids if str(d).strip()]

    CONFIG['city_ids'] = [city_id]
    CONFIG['category'] = str(filters.get('category') or 'apartment-rent')
    CONFIG['district_ids'] = district_ids
    CONFIG['max_items'] = max_items
    CONFIG['max_workers'] = DETAIL_WORKERS
    CONFIG['search_filters'] = filters.get('search_filters') or {}
    CONFIG['search_query'] = str(filters.get('search_query') or '').strip()
    CONFIG['network_error'] = None
    CONFIG['last_request_error'] = None


def _collect_divar_items(filters: Dict[str, Any], max_items: int) -> List[Dict[str, Any]]:
    (
        CONFIG,
        fetch_post_tokens,
        fetch_post_detail,
        get_http_session,
    ) = _ensure_scraper_import()
    _configure_scraper(CONFIG, filters, max_items)

    tokens = fetch_post_tokens()
    if not tokens:
        network_error = CONFIG.get('network_error')
        if network_error:
            raise RuntimeError(str(network_error))
        raise ValueError('آگهی‌ای از دیوار یافت نشد.')

    session = get_http_session()
    items: List[Dict[str, Any]] = []
    workers = max(1, min(DETAIL_WORKERS, int(CONFIG.get('max_workers', DETAIL_WORKERS))))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_post_detail, token, session): token for token in tokens}
        for fut in as_completed(futures):
            token = futures[fut]
            try:
                detail = fut.result()
            except Exception:
                detail = None
            if not detail:
                continue
            items.append({'token': token, 'raw': detail})
            if len(items) >= max_items:
                break

    if not items:
        raise ValueError('جزئیات آگهی از دیوار دریافت نشد.')
    return items


def _mark_failed(job_id: int, message: str) -> None:
    MobileCloudExtractionJob.objects.filter(pk=job_id).update(
        status=MobileCloudExtractionJob.STATUS_FAILED,
        error=(message or '')[:4000],
        finished_at=timezone.now(),
    )


def _run_job_inner(job_id: int) -> None:
    close_old_connections()
    job = MobileCloudExtractionJob.objects.select_related('user').filter(pk=job_id).first()
    if not job:
        return
    if job.status != MobileCloudExtractionJob.STATUS_QUEUED:
        return

    now = timezone.now()
    job.status = MobileCloudExtractionJob.STATUS_RUNNING
    job.started_at = now
    job.error = ''
    job.save(update_fields=['status', 'started_at', 'error'])

    user = job.user
    filters = dict(job.filters or {})
    filters['source_client'] = 'cloud_extract'
    filters['max_items'] = job.max_items

    try:
        check_mobile_extraction_allowed(user)
        started_at = timezone.now()
        items = _collect_divar_items(filters, job.max_items)
        result = ingest_mobile_extraction(user, {
            'filters': filters,
            'items': items,
            'started_at': started_at.isoformat(),
            'finished_at': timezone.now().isoformat(),
        })
        MobileCloudExtractionJob.objects.filter(pk=job_id).update(
            status=MobileCloudExtractionJob.STATUS_SUCCESS,
            dataset_id=result.dataset.pk,
            ingested_count=result.ingested_count,
            error='',
            finished_at=timezone.now(),
        )
    except Exception as exc:
        logger.exception('cloud extraction job %s failed', job_id)
        _mark_failed(job_id, str(exc))
    finally:
        close_old_connections()


def run_job(job_id: int) -> None:
    acquired = _JOB_SEMAPHORE.acquire(blocking=False)
    if not acquired:
        _mark_failed(job_id, 'سرور مشغول است؛ لطفاً چند دقیقه دیگر دوباره تلاش کنید.')
        return
    try:
        _run_job_inner(job_id)
    finally:
        _JOB_SEMAPHORE.release()
