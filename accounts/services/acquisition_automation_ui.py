"""UI helpers for Acquisition Automation in Lead Acquisition Center."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.models import AcquisitionAutomationCampaign, AcquisitionRun, LeadImportBatch


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


def _places_file_path() -> Optional[Path]:
    pd = (getattr(settings, 'PHONE_DETECTOR_DIR', None) or '').strip()
    candidates: list[Path] = []
    if pd:
        root = Path(pd).expanduser().resolve().parent
        candidates.append(root / 'config' / 'places-web.json')
        candidates.append(Path(pd).expanduser().resolve() / 'config' / 'places-web.json')
    base = Path(getattr(settings, 'BASE_DIR', Path.cwd()))
    candidates.extend([
        base.parent / 'config' / 'places-web.json',
        Path('/root/config/places-web.json'),
    ])
    for path in candidates:
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=1)
def _load_places_raw() -> list[dict]:
    path = _places_file_path()
    if not path:
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def places_config_available() -> bool:
    return bool(_load_places_raw())


def list_automation_cities(*, limit: int = 80) -> list[dict]:
    """شهرهای type=2 برای dropdown."""
    rows = []
    for item in _load_places_raw():
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


def list_districts_for_city(city_name: str, *, limit: int = 400) -> list[str]:
    city_name = (city_name or '').strip()
    if not city_name:
        return []
    places = _load_places_raw()
    city_id = None
    for item in places:
        if str(item.get('type')) == '2' and str(item.get('name') or '').strip() == city_name:
            city_id = item.get('id')
            break
    if city_id is None:
        return []
    names: list[str] = []
    for item in places:
        if item.get('parent') == city_id and str(item.get('type')) == '4':
            name = str(item.get('name') or '').strip()
            if name:
                names.append(name)
    return sorted(set(names))[:limit]


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


def automation_overview_stats() -> dict:
    now = timezone.now()
    campaigns = AcquisitionAutomationCampaign.objects.all()
    runs = AcquisitionRun.objects.all()
    last_24h = now - timezone.timedelta(hours=24)

    return {
        'campaigns_total': campaigns.count(),
        'campaigns_active': campaigns.filter(is_active=True).count(),
        'runs_total': runs.count(),
        'runs_queued': runs.filter(status=AcquisitionRun.Status.QUEUED).count(),
        'runs_running': runs.filter(status=AcquisitionRun.Status.RUNNING).count(),
        'runs_ingested_24h': runs.filter(
            status=AcquisitionRun.Status.INGESTED,
            finished_at__gte=last_24h,
        ).count(),
        'phones_24h': runs.filter(finished_at__gte=last_24h).aggregate(
            total=Sum('phones_extracted'),
        )['total'] or 0,
        'worker_lock': bool(cache.get('acquisition_automation:running')),
        'places_available': places_config_available(),
        'places_path_hint': str(_places_file_path() or '—'),
    }


def automation_campaigns_for_ui(*, limit: int = 30) -> list[dict]:
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
        rows.append({
            'campaign': c,
            'runs_count': c.runs_count,
            'ingested_count': c.ingested_count,
            'last_run': last_run,
            'districts_display': ' · '.join(c.districts or []) or '—',
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
        limit_per_run = max(5, min(500, int(data.get('limit_per_run') or 30)))
    except (TypeError, ValueError):
        limit_per_run = 30
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

    campaign.name = name
    campaign.city = city
    campaign.districts = districts
    campaign.category = (data.get('category') or campaign.category).strip()
    try:
        campaign.limit_per_run = max(5, min(500, int(data.get('limit_per_run') or campaign.limit_per_run)))
    except (TypeError, ValueError):
        pass
    try:
        campaign.interval_hours = max(1, min(168, int(data.get('interval_hours') or campaign.interval_hours)))
    except (TypeError, ValueError):
        pass
    if 'is_active' in data:
        campaign.is_active = bool(data.get('is_active'))
    if 'auto_create_campaign' in data:
        campaign.auto_create_campaign = bool(data.get('auto_create_campaign'))
    if 'auto_enroll_pilot' in data:
        campaign.auto_enroll_pilot = bool(data.get('auto_enroll_pilot'))
    if data.get('landing_url'):
        campaign.landing_url = str(data.get('landing_url')).strip()
    campaign.save()
    return campaign


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


def queue_automation_run_now(campaign_id: int) -> AcquisitionRun:
    """یک run فوری در صف — بدون انتظار cron."""
    from accounts.services.acquisition_automation import has_active_run, pick_district

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
    now = timezone.now()
    run = AcquisitionRun.objects.create(
        campaign=campaign,
        status=AcquisitionRun.Status.QUEUED,
        district=district,
        metrics={'category': campaign.category, 'limit': campaign.limit_per_run, 'manual': True},
    )
    campaign.last_run_at = now
    campaign.next_run_at = now + timezone.timedelta(hours=max(1, int(campaign.interval_hours or 6)))
    campaign.save(update_fields=['last_run_at', 'next_run_at'])
    return run
