"""UI helpers for Acquisition Automation in Lead Acquisition Center."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional

from accounts.services.divar_places import (
    _load_places_raw,
    _places_file_path,
    list_districts_for_city,
    places_config_available,
)
from django.core.cache import cache
from django.db.models import Count, Min, Q, Sum
from django.utils import timezone

from accounts.models import (
    AcquisitionAutomationCampaign,
    AcquisitionRun,
    LeadImportBatch,
    PhoneDetectorExtractionLine,
)


class AutomationUIError(Exception):
    def __init__(self, message: str, *, code: str = 'automation_error'):
        self.message = message
        self.code = code
        super().__init__(message)


CATEGORY_CHOICES = (
    ('apartment-sell', 'فروش آپارتمان'),
    ('apartment-rent', 'رهن و اجاره آپارتمان'),
    ('villa-sell', 'فروش ویلا'),
    ('villa-rent', 'رهن و اجاره ویلا'),
)


def list_automation_cities(*, limit: int = 80) -> list[dict]:
    """شهرهای type=2 برای dropdown."""
    _id_to_node, raw = _load_places_raw()
    rows = []
    for item in raw:
        if str(item.get('type')) != '2':
            continue
        name = str(item.get('name') or '').strip()
        if not name or name.startswith('کل '):
            continue
        rows.append({
            'id': item.get('id'),
            'name': name,
            'slug': item.get('slug') or '',
        })
    rows.sort(key=lambda r: (r['name'] != 'تهران', r['name']))
    return rows[:limit]


def _form_bool(value) -> bool:
    return str(value or '').lower() in ('1', 'true', 'on', 'yes')


def parse_districts_input(raw: str) -> list[str]:
    text = (raw or '').replace('\r', '\n').strip()
    if not text:
        return []
    if text.startswith('['):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            pass
    parts: list[str] = []
    for line in text.replace(',', '\n').split('\n'):
        bit = line.strip()
        if bit:
            parts.append(bit)
    return parts


def _acquisition_run_snapshot(run: Optional[AcquisitionRun]) -> Optional[dict]:
    if run is None:
        return None
    campaign_name = ''
    if run.campaign_id:
        campaign_name = (run.campaign.name or '').strip()
    return {
        'id': run.pk,
        'status': run.status,
        'status_label': run.get_status_display(),
        'district': (run.district or '').strip() or '—',
        'campaign_name': campaign_name or '—',
        'phones_extracted': int(run.phones_extracted or 0),
    }


def automation_overview_stats() -> dict:
    now = timezone.now()
    campaigns = AcquisitionAutomationCampaign.objects.all()
    runs = AcquisitionRun.objects.all()
    last_24h = now - timezone.timedelta(hours=24)

    active_campaigns = campaigns.filter(is_active=True)
    campaigns_due = active_campaigns.filter(
        Q(next_run_at__isnull=True) | Q(next_run_at__lte=now),
    ).count()
    next_run_at = active_campaigns.filter(next_run_at__isnull=False).aggregate(
        next_at=Min('next_run_at'),
    )['next_at']

    running_run = (
        runs.filter(status=AcquisitionRun.Status.RUNNING)
        .select_related('campaign')
        .order_by('-started_at', '-pk')
        .first()
    )
    queued_head = (
        runs.filter(status=AcquisitionRun.Status.QUEUED)
        .select_related('campaign')
        .order_by('created_at', 'pk')
        .first()
    )
    focus_run = running_run or queued_head

    finished_24h = runs.filter(finished_at__gte=last_24h)
    ingested_24h = finished_24h.filter(status=AcquisitionRun.Status.INGESTED)
    failed_24h = runs.filter(
        status=AcquisitionRun.Status.FAILED,
        finished_at__gte=last_24h,
    ).count()

    lines = PhoneDetectorExtractionLine.objects.all()
    line_ops = PhoneDetectorExtractionLine.OperationalStatus
    lines_ready = lines.filter(operational_status=line_ops.ACTIVE).count()
    lines_running = lines.filter(operational_status=line_ops.RUNNING).count()
    lines_blocked = lines.filter(
        operational_status__in=(
            line_ops.BLOCKED_CAPTCHA,
            line_ops.COOLDOWN,
            line_ops.PAUSED,
            line_ops.ERROR,
        ),
    ).count()

    places_ok = places_config_available()
    places_districts_tehran = len(list_districts_for_city('تهران')) if places_ok else 0

    return {
        'campaigns_total': campaigns.count(),
        'campaigns_active': active_campaigns.count(),
        'campaigns_due': campaigns_due,
        'next_run_at': next_run_at,
        'runs_total': runs.count(),
        'runs_queued': runs.filter(status=AcquisitionRun.Status.QUEUED).count(),
        'runs_running': runs.filter(status=AcquisitionRun.Status.RUNNING).count(),
        'runs_ingested_24h': ingested_24h.count(),
        'runs_failed_24h': failed_24h,
        'phones_24h': finished_24h.aggregate(total=Sum('phones_extracted'))['total'] or 0,
        'phones_ingested_24h': ingested_24h.aggregate(total=Sum('phones_extracted'))['total'] or 0,
        'import_batches_24h': ingested_24h.filter(import_batch__isnull=False).count(),
        'focus_run': _acquisition_run_snapshot(focus_run),
        'worker_lock': bool(cache.get('acquisition_automation:running')),
        'lines_total': lines.count(),
        'lines_ready': lines_ready,
        'lines_running': lines_running,
        'lines_blocked': lines_blocked,
        'places_available': places_ok,
        'places_districts_tehran': places_districts_tehran,
        'places_path_hint': str(_places_file_path() or '—'),
    }


_CATEGORY_LABELS = dict(CATEGORY_CHOICES)


def _automation_category_label(value: str) -> str:
    from accounts.services.lead_import import listing_category_display_fa

    return listing_category_display_fa(value)


def automation_campaigns_for_ui(*, limit: int = 30) -> list[dict]:
    from accounts.services.acquisition_automation import district_rotation_info

    qs = (
        AcquisitionAutomationCampaign.objects.annotate(
            runs_count=Count('runs'),
            ingested_count=Count(
                'runs',
                filter=Q(runs__status=AcquisitionRun.Status.INGESTED),
            ),
        )
        .order_by('-is_active', 'next_run_at', '-created_at')[:limit]
    )
    rows: list[dict] = []
    for c in qs:
        last_run = c.runs.order_by('-created_at').first()
        districts = list(c.districts or [])
        rot = district_rotation_info(c)
        if len(districts) <= 4:
            districts_display = ' · '.join(districts) or '—'
        else:
            districts_display = f'{len(districts)} منطقه · {districts[0]} … {districts[-1]}'
        rows.append({
            'campaign': c,
            'runs_count': c.runs_count,
            'ingested_count': c.ingested_count,
            'last_run': last_run,
            'districts_display': districts_display,
            'districts_count': len(districts),
            'rotation': rot,
            'category_label': _automation_category_label(c.category),
        })
    return rows


def automation_runs_for_ui(*, limit: int = 25) -> list[AcquisitionRun]:
    return list(
        AcquisitionRun.objects.select_related(
            'campaign', 'import_batch', 'lead_campaign',
        ).order_by('-created_at')[:limit],
    )


def create_automation_campaign_from_form(data: dict) -> AcquisitionAutomationCampaign:
    name = (data.get('name') or '').strip()
    city = (data.get('city') or 'تهران').strip()
    districts = parse_districts_input(data.get('districts') or '')
    if not name:
        raise AutomationUIError('نام کمپین الزامی است.', code='missing_name')
    if not districts:
        raise AutomationUIError('حداقل یک منطقه انتخاب یا وارد کنید.', code='missing_districts')

    category = (data.get('category') or 'apartment-sell').strip()
    try:
        limit_per_run = max(5, min(40, int(data.get('limit_per_run') or 20)))
    except (TypeError, ValueError):
        limit_per_run = 20
    try:
        min_phones = max(5, min(40, int(data.get('min_phones_per_district') or 20)))
    except (TypeError, ValueError):
        min_phones = 20
    try:
        interval_hours = max(1, min(168, int(data.get('interval_hours') or 6)))
    except (TypeError, ValueError):
        interval_hours = 6

    return AcquisitionAutomationCampaign.objects.create(
        name=name,
        city=city,
        districts=districts,
        category=category,
        limit_per_run=limit_per_run,
        min_phones_per_district=min_phones,
        interval_hours=interval_hours,
        is_active=bool(data.get('is_active', True)),
        auto_create_campaign=bool(data.get('auto_create_campaign', True)),
        auto_enroll_pilot=bool(data.get('auto_enroll_pilot', True)),
        landing_url=(data.get('landing_url') or 'https://divarfiling.ir/').strip(),
        next_run_at=None,
    )


def update_automation_campaign_from_form(campaign_id: int, data: dict) -> AcquisitionAutomationCampaign:
    campaign = AcquisitionAutomationCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        raise AutomationUIError('کمپین یافت نشد.', code='not_found')

    name = (data.get('name') or campaign.name).strip()
    city = (data.get('city') or campaign.city).strip()
    districts_raw = data.get('districts')
    districts = parse_districts_input(districts_raw) if districts_raw is not None else list(campaign.districts or [])
    if not name:
        raise AutomationUIError('نام کمپین الزامی است.', code='missing_name')
    if not districts:
        raise AutomationUIError('حداقل یک منطقه لازم است.', code='missing_districts')

    old_districts = list(campaign.districts or [])
    if districts != old_districts:
        campaign.district_cursor = 0
    if data.get('reset_district_rotation'):
        campaign.district_cursor = 0

    campaign.name = name
    campaign.city = city
    campaign.districts = districts
    campaign.category = (data.get('category') or campaign.category).strip()
    try:
        campaign.limit_per_run = max(5, min(40, int(data.get('limit_per_run') or campaign.limit_per_run)))
    except (TypeError, ValueError):
        pass
    try:
        campaign.min_phones_per_district = max(
            5,
            min(40, int(data.get('min_phones_per_district') or campaign.min_phones_per_district)),
        )
    except (TypeError, ValueError):
        pass
    try:
        campaign.interval_hours = max(1, min(168, int(data.get('interval_hours') or campaign.interval_hours)))
    except (TypeError, ValueError):
        pass
    if 'is_active' in data:
        campaign.is_active = _form_bool(data.get('is_active'))
    if 'auto_create_campaign' in data:
        campaign.auto_create_campaign = _form_bool(data.get('auto_create_campaign'))
    if 'auto_enroll_pilot' in data:
        campaign.auto_enroll_pilot = _form_bool(data.get('auto_enroll_pilot'))
    if data.get('landing_url'):
        campaign.landing_url = str(data.get('landing_url')).strip()
    campaign.save()
    return campaign


def delete_automation_campaign(campaign_id: int) -> dict[str, Any]:
    """حذف کمپین جمع‌آوری خودکار — اجراها CASCADE؛ LeadCampaign و سرنخ‌ها باقی می‌مانند."""
    campaign = AcquisitionAutomationCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        raise AutomationUIError('کمپین یافت نشد.', code='not_found')

    busy = AcquisitionRun.objects.filter(
        campaign=campaign,
        status__in=(
            AcquisitionRun.Status.QUEUED,
            AcquisitionRun.Status.RUNNING,
        ),
    ).exists()
    if busy:
        raise AutomationUIError(
            'اجرای این کمپین در صف یا در حال اجراست — ابتدا متوقف کنید یا تا پایان اجرا صبر کنید.',
            code='run_busy',
        )

    name = campaign.name
    runs_removed = campaign.runs.count()
    campaign.delete()
    return {'name': name, 'runs_removed': runs_removed}


def toggle_automation_campaign(campaign_id: int, *, active: Optional[bool] = None) -> AcquisitionAutomationCampaign:
    campaign = AcquisitionAutomationCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        raise AutomationUIError('کمپین یافت نشد.', code='not_found')
    campaign.is_active = not campaign.is_active if active is None else bool(active)
    campaign.save(update_fields=['is_active'])
    return campaign


def reset_automation_schedule(campaign_id: int) -> AcquisitionAutomationCampaign:
    """اجرای بعدی را فوری می‌کند (next_run_at = null)."""
    campaign = AcquisitionAutomationCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        raise AutomationUIError('کمپین یافت نشد.', code='not_found')
    campaign.next_run_at = None
    campaign.save(update_fields=['next_run_at'])
    return campaign


def reset_automation_district_rotation(campaign_id: int) -> AcquisitionAutomationCampaign:
    """چرخش مناطق را از اولین منطقه دوباره شروع کن."""
    campaign = AcquisitionAutomationCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        raise AutomationUIError('کمپین یافت نشد.', code='not_found')
    campaign.district_cursor = 0
    campaign.save(update_fields=['district_cursor'])
    return campaign


def queue_automation_run_now(campaign_id: int) -> AcquisitionRun:
    """یک run فوری در صف — بدون انتظار cron."""
    from accounts.services.acquisition_automation import (
        district_rotation_info,
        has_active_run,
        pick_district,
    )

    if has_active_run():
        raise AutomationUIError(
            'یک اجرای دیگر در صف یا در حال اجراست. کمی بعد تلاش کنید.',
            code='run_busy',
        )
    if cache.get('acquisition_automation:running'):
        raise AutomationUIError('Worker مشغول است.', code='worker_lock')

    campaign = AcquisitionAutomationCampaign.objects.filter(pk=campaign_id, is_active=True).first()
    if not campaign:
        raise AutomationUIError('کمپین فعال یافت نشد.', code='not_found')

    district = pick_district(campaign)
    rot = district_rotation_info(campaign)
    now = timezone.now()
    run = AcquisitionRun.objects.create(
        campaign=campaign,
        status=AcquisitionRun.Status.QUEUED,
        district=district,
        metrics={
            'category': campaign.category,
            'limit': campaign.limit_per_run,
            'manual': True,
            'district_index': rot['current_index'],
            'district_total': rot['total'],
        },
    )
    campaign.last_run_at = now
    campaign.next_run_at = now + timezone.timedelta(hours=max(1, int(campaign.interval_hours or 6)))
    campaign.save(update_fields=['last_run_at', 'next_run_at'])
    return run
