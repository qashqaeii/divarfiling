"""اتوماسیون جمع‌آوری لید: phone-detector → Lead Acquisition Center."""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    AcquisitionAutomationCampaign,
    AcquisitionRun,
    LeadImportBatch,
    LeadList,
)
from accounts.services.lead_campaign_send import (
    auto_create_campaign_for_import,
    enroll_pilot,
    eligible_count_for_list,
)
from accounts.services.lead_import import (
    LeadImportError,
    commit_import_batch,
    create_preview_batch,
    preview_phone_detector_json,
)

logger = logging.getLogger(__name__)

LOCK_KEY = 'acquisition_automation:running'
DEFAULT_LOCK_TTL = 60 * 60 * 4  # 4 hours
DEFAULT_COOLDOWN_HOURS = 4


def _automation_enabled() -> bool:
    return bool(getattr(settings, 'ACQUISITION_AUTOMATION_ENABLED', True))


def _cooldown_hours() -> int:
    return int(getattr(settings, 'ACQUISITION_COOLDOWN_HOURS', DEFAULT_COOLDOWN_HOURS))


def acquire_run_lock(*, ttl: int = DEFAULT_LOCK_TTL) -> bool:
    return cache.add(LOCK_KEY, '1', timeout=ttl)


def release_run_lock() -> None:
    cache.delete(LOCK_KEY)


def has_active_run() -> bool:
    return AcquisitionRun.objects.filter(
        status__in=(
            AcquisitionRun.Status.QUEUED,
            AcquisitionRun.Status.RUNNING,
        ),
    ).exists()


def normalized_districts(campaign: AcquisitionAutomationCampaign) -> list[str]:
    return [str(d).strip() for d in (campaign.districts or []) if str(d).strip()]


def pick_district(campaign: AcquisitionAutomationCampaign) -> str:
    """منطقه فعلی طبق district_cursor — هر run فقط یک منطقه."""
    districts = normalized_districts(campaign)
    if not districts:
        raise ValueError(f'کمپین #{campaign.pk} منطقه‌ای ندارد.')
    idx = int(campaign.district_cursor or 0) % len(districts)
    return districts[idx]


def district_rotation_info(campaign: AcquisitionAutomationCampaign) -> dict:
    districts = normalized_districts(campaign)
    total = len(districts)
    if total == 0:
        return {
            'current': '',
            'current_index': 0,
            'total': 0,
            'next': '',
            'progress_label': '—',
        }
    idx = int(campaign.district_cursor or 0) % total
    nxt = districts[(idx + 1) % total]
    return {
        'current': districts[idx],
        'current_index': idx + 1,
        'total': total,
        'next': nxt,
        'progress_label': f'{idx + 1}/{total}',
    }


def advance_district_cursor(campaign_id: int) -> None:
    """پس از پایان هر run به منطقه بعدی برو (چرخشی)."""
    campaign = AcquisitionAutomationCampaign.objects.filter(pk=campaign_id).only(
        'id', 'district_cursor', 'districts',
    ).first()
    if not campaign:
        return
    total = len(normalized_districts(campaign))
    if total <= 1:
        return
    nxt = (int(campaign.district_cursor or 0) + 1) % total
    AcquisitionAutomationCampaign.objects.filter(pk=campaign_id).update(district_cursor=nxt)


def schedule_due_campaigns(*, max_jobs: int = 1) -> list[AcquisitionRun]:
    """کمپین‌های سررسید را به صف اجرا اضافه می‌کند."""
    if not _automation_enabled():
        return []

    if has_active_run():
        return []

    if cache.get(LOCK_KEY):
        return []

    from accounts.services.extraction_lines_reconcile import reconcile_extraction_lines
    from accounts.services.phone_detector_line_ops import (
        count_schedulable_lines,
        operational_summary,
    )

    reconcile_extraction_lines()
    lines_summary = operational_summary()

    now = timezone.now()
    created: list[AcquisitionRun] = []

    campaigns = (
        AcquisitionAutomationCampaign.objects.filter(is_active=True)
        .order_by('next_run_at', 'last_run_at', 'id')
    )

    for campaign in campaigns:
        if len(created) >= max_jobs:
            break
        if campaign.next_run_at and campaign.next_run_at > now:
            continue

        if lines_summary.get('total_lines') and count_schedulable_lines() == 0:
            logger.info(
                'Skipping campaign %s — no schedulable extraction lines (waiting for healthy line)',
                campaign.pk,
            )
            if not campaign.next_run_at or campaign.next_run_at <= now:
                campaign.next_run_at = now + timedelta(
                    hours=max(1, int(campaign.interval_hours or 6)),
                )
                campaign.save(update_fields=['next_run_at'])
            continue

        district = pick_district(campaign)
        rot = district_rotation_info(campaign)
        run = AcquisitionRun.objects.create(
            campaign=campaign,
            status=AcquisitionRun.Status.QUEUED,
            district=district,
            metrics={
                'category': campaign.category,
                'limit': campaign.limit_per_run,
                'district_index': rot['current_index'],
                'district_total': rot['total'],
            },
        )
        campaign.last_run_at = now
        campaign.next_run_at = now + timedelta(hours=max(1, int(campaign.interval_hours or 6)))
        campaign.save(update_fields=['last_run_at', 'next_run_at'])

        created.append(run)
        logger.info('Queued acquisition run #%s for campaign %s (%s)', run.pk, campaign.pk, district)

    return created


def _load_run_json_bytes(run: AcquisitionRun) -> bytes:
    if run.output_json:
        if isinstance(run.output_json, (dict, list)):
            return json.dumps(run.output_json, ensure_ascii=False).encode('utf-8')
        return str(run.output_json).encode('utf-8')
    if run.output_path:
        path = Path(run.output_path)
        if path.is_file():
            return path.read_bytes()
    raise LeadImportError('خروجی JSON برای این اجرا یافت نشد.', code='missing_output')


def _apply_output_metrics(run: AcquisitionRun, payload: dict) -> None:
    meta = payload.get('metadata') or {}
    consultants = payload.get('consultants') or []
    run.scanned_posts = int(meta.get('scanned_posts') or meta.get('tokens_scanned') or 0)
    run.consultants_found = int(meta.get('total_consultants') or len(consultants))
    run.phones_extracted = int(
        meta.get('with_phone_count')
        or sum(1 for c in consultants if c.get('phone'))
    )
    run.metrics = {
        **(run.metrics or {}),
        'hip_stats': meta.get('hip_stats') or {},
        'source_metadata': {
            k: meta.get(k)
            for k in ('mode', 'requested_limit', 'status', 'scraped_at')
            if k in meta
        },
    }


@transaction.atomic
def ingest_acquisition_run(run: AcquisitionRun) -> dict:
    """
    JSON خروجی phone-detector را از طریق pipeline موجود وارد مرکز جذب می‌کند.
    lead_import.py و lead_campaign_send.py بدون تغییر منطق فراخوانی می‌شوند.
    """
    run = AcquisitionRun.objects.select_for_update().select_related('campaign').get(pk=run.pk)
    if run.status == AcquisitionRun.Status.INGESTED:
        return {'run_id': run.pk, 'skipped': True, 'reason': 'already_ingested'}

    raw = _load_run_json_bytes(run)
    preview = preview_phone_detector_json(raw, filename=f'auto-run-{run.pk}.json')

    if preview.duplicate_file:
        run.status = AcquisitionRun.Status.INGESTED
        run.error_message = 'فایل تکراری — قبلاً import شده.'
        if preview.existing_batch_id:
            run.import_batch_id = preview.existing_batch_id
        run.save()
        return {
            'run_id': run.pk,
            'skipped': True,
            'reason': 'duplicate_file',
            'batch_id': preview.existing_batch_id,
        }

    batch = create_preview_batch(preview, uploaded_by=None)
    batch.acquisition_run = run
    batch.original_filename = batch.original_filename or f'auto-run-{run.pk}.json'
    batch.save(update_fields=['acquisition_run', 'original_filename'])

    result = commit_import_batch(batch.pk, preview_rows=preview.rows)

    campaign_cfg = run.campaign
    lead_campaign = None
    enroll_stats: Optional[dict] = None

    if campaign_cfg.auto_create_campaign:
        lead_list = LeadList.objects.get(pk=result['list_id'])
        eligible = result.get('members_added', 0) or preview.stats.get('eligible', 0)
        if eligible <= 0:
            eligible = eligible_count_for_list(lead_list)
        lead_campaign = auto_create_campaign_for_import(
            lead_list=lead_list,
            batch_id=result['batch_id'],
            eligible_count=eligible,
            landing_url=campaign_cfg.landing_url or 'https://divarfiling.ir/',
        )
        if lead_campaign and campaign_cfg.auto_enroll_pilot:
            enroll_stats = enroll_pilot(lead_campaign)

    run.import_batch_id = result['batch_id']
    run.lead_campaign = lead_campaign
    run.status = AcquisitionRun.Status.INGESTED
    run.save(
        update_fields=[
            'import_batch_id',
            'lead_campaign',
            'status',
        ],
    )

    return {
        'run_id': run.pk,
        'batch_id': result['batch_id'],
        'list_id': result['list_id'],
        'created': result.get('created', 0),
        'updated': result.get('updated', 0),
        'members_added': result.get('members_added', 0),
        'lead_campaign_id': lead_campaign.pk if lead_campaign else None,
        'enroll': enroll_stats,
    }


def mark_run_running(run_id: int) -> Optional[AcquisitionRun]:
    updated = AcquisitionRun.objects.filter(
        pk=run_id,
        status=AcquisitionRun.Status.QUEUED,
    ).update(
        status=AcquisitionRun.Status.RUNNING,
        started_at=timezone.now(),
    )
    if not updated:
        return None
    return AcquisitionRun.objects.select_related('campaign').filter(pk=run_id).first()


def finalize_run_from_worker(
    run_id: int,
    *,
    worker_status: str,
    output_path: str = '',
    output_payload: Optional[dict] = None,
    error_message: str = '',
    metrics: Optional[dict] = None,
    auto_ingest: bool = True,
) -> Dict[str, Any]:
    """Worker پس از extraction وضعیت run را ثبت و در صورت موفقیت ingest می‌kند."""
    run = AcquisitionRun.objects.select_related('campaign').filter(pk=run_id).first()
    if not run:
        return {'error': 'run_not_found'}

    run.finished_at = timezone.now()
    run.metrics = {**(run.metrics or {}), **(metrics or {})}
    summary_message = (metrics or {}).get('summary_message') or ''
    run.error_message = summary_message or error_message or ''

    if output_path:
        run.output_path = output_path
    if output_payload:
        run.output_json = output_payload
        _apply_output_metrics(run, output_payload)
    elif output_path:
        path = Path(output_path)
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding='utf-8-sig'))
                run.output_json = payload
                _apply_output_metrics(run, payload)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning('Could not parse output JSON for run %s: %s', run_id, exc)

    status_map = {
        'completed': AcquisitionRun.Status.COMPLETED,
        'rate_limited': AcquisitionRun.Status.RATE_LIMITED,
        'failed': AcquisitionRun.Status.FAILED,
    }
    run.status = status_map.get(worker_status, AcquisitionRun.Status.FAILED)
    run.save()

    line_outcome = (metrics or {}).get('line_outcome') or {}

    if worker_status == 'rate_limited':
        all_lines_blocked = bool(line_outcome.get('all_lines_blocked'))
        if all_lines_blocked:
            campaign = AcquisitionAutomationCampaign.objects.filter(pk=run.campaign_id).first()
            hours = _cooldown_hours()
            if campaign:
                hours = max(hours, int(campaign.interval_hours or 6))
            cooldown = timezone.now() + timedelta(hours=hours)
            AcquisitionAutomationCampaign.objects.filter(pk=run.campaign_id).update(
                next_run_at=cooldown,
            )
        if not run.error_message:
            run.error_message = summary_message or (
                'تمام خطوط استخراج محدود یا غیرفعال — تا آماده‌شدن خط سالم صبر می‌شود.'
            )
            run.save(update_fields=['error_message'])

    ingest_result: dict = {}
    can_ingest = worker_status == 'completed'
    if worker_status == 'rate_limited':
        can_ingest = bool(run.phones_extracted) or bool(
            (run.output_json or {}).get('consultants') if isinstance(run.output_json, dict) else False
        )

    if auto_ingest and can_ingest and (run.output_json or run.output_path):
        try:
            ingest_result = ingest_acquisition_run(run)
        except LeadImportError as exc:
            run.status = AcquisitionRun.Status.FAILED
            run.error_message = exc.message
            run.save(update_fields=['status', 'error_message'])
            ingest_result = {'error': exc.message, 'code': exc.code}
        except Exception as exc:
            logger.exception('ingest failed for run %s', run_id)
            run.status = AcquisitionRun.Status.FAILED
            run.error_message = str(exc)
            run.save(update_fields=['status', 'error_message'])
            ingest_result = {'error': str(exc)}

    # هر run (موفق یا captcha) → منطقه بعدی در اجرای بعدی
    if worker_status in ('completed', 'rate_limited', 'failed', 'ingested'):
        advance_district_cursor(run.campaign_id)

    release_run_lock()
    return {
        'run_id': run_id,
        'status': run.status,
        'ingest': ingest_result,
    }


def fetch_next_queued_run() -> Optional[AcquisitionRun]:
    from divar_shop.db_lifecycle import run_db_with_retry

    def _query() -> Optional[AcquisitionRun]:
        return (
            AcquisitionRun.objects.filter(status=AcquisitionRun.Status.QUEUED)
            .select_related('campaign')
            .order_by('created_at', 'id')
            .first()
        )

    return run_db_with_retry(_query, label='fetch_next_queued_run')
