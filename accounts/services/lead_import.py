"""ایمپورت حرفه‌ای سرنخ از JSON phone-detector."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from accounts.models import (
    LeadImportBatch,
    LeadList,
    LeadListMember,
    MarketingLead,
    SuppressionEntry,
)
from accounts.phone_utils import find_user_by_phone, is_valid_iran_mobile, normalize_phone


AGENCY_HINTS = (
    'آژانس',
    'مسکن',
    'املاک',
    'گروه',
    'گروپ',
    'هلدینگ',
    'شرکت',
    'بنگاه',
)


@dataclass
class PreviewRow:
    phone: str
    name: str
    district: str
    category: str
    outcome: str
    lead_type: str = MarketingLead.LeadType.UNKNOWN
    confidence: Decimal = Decimal('0.00')


@dataclass
class ImportPreview:
    rows: List[PreviewRow] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_hash: str = ''
    duplicate_file: bool = False
    existing_batch_id: Optional[int] = None


class LeadImportError(Exception):
    def __init__(self, message: str, *, code: str = 'import_error'):
        self.message = message
        self.code = code
        super().__init__(message)


def compute_file_hash(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def classify_lead_name(name: str) -> tuple[str, Decimal]:
    text = (name or '').strip()
    if not text:
        return MarketingLead.LeadType.UNKNOWN, Decimal('0.00')
    lowered = text.lower()
    hits = sum(1 for h in AGENCY_HINTS if h in text or h.lower() in lowered)
    if hits >= 2:
        return MarketingLead.LeadType.AGENCY, Decimal('0.55')
    if hits == 1:
        return MarketingLead.LeadType.AGENCY, Decimal('0.35')
    # نام کوتاه شخصی‌مانند
    if len(text.split()) <= 3 and not any(h in text for h in AGENCY_HINTS):
        return MarketingLead.LeadType.CONSULTANT, Decimal('0.25')
    return MarketingLead.LeadType.UNKNOWN, Decimal('0.10')


def _parse_payload(raw_bytes: bytes) -> dict:
    try:
        data = json.loads(raw_bytes.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LeadImportError('فایل JSON معتبر نیست.', code='bad_json') from exc
    if not isinstance(data, dict):
        raise LeadImportError('ساختار JSON باید object باشد.', code='bad_structure')
    consultants = data.get('consultants')
    if not isinstance(consultants, list):
        raise LeadImportError('کلید consultants یافت نشد.', code='missing_consultants')
    return data


def preview_phone_detector_json(
    raw_bytes: bytes,
    *,
    filename: str = '',
) -> ImportPreview:
    file_hash = compute_file_hash(raw_bytes)
    existing = LeadImportBatch.objects.filter(file_hash=file_hash).first()
    if existing and existing.status == LeadImportBatch.Status.COMMITTED:
        return ImportPreview(
            file_hash=file_hash,
            duplicate_file=True,
            existing_batch_id=existing.pk,
            stats={'duplicate_file': 1},
            metadata={'original_filename': filename},
        )

    data = _parse_payload(raw_bytes)
    meta = data.get('metadata') or {}
    city = str(meta.get('city') or '')
    district = str(meta.get('district') or '')
    category = str(meta.get('category') or '')

    stats = {
        'read': 0,
        'valid': 0,
        'invalid': 0,
        'duplicate_in_file': 0,
        'already_lead': 0,
        'existing_user': 0,
        'suppressed': 0,
        'eligible': 0,
    }
    seen_in_file: set[str] = set()
    rows: List[PreviewRow] = []

    for item in data.get('consultants') or []:
        if not isinstance(item, dict):
            continue
        stats['read'] += 1
        phone = normalize_phone(str(item.get('phone') or ''))
        name = str(item.get('consultant_name') or item.get('title') or '')[:255]
        row_district = resolve_district_label(meta_district=district, item_district=str(item.get('district') or ''))
        lead_type, confidence = classify_lead_name(name)

        if not is_valid_iran_mobile(phone):
            stats['invalid'] += 1
            rows.append(PreviewRow(phone=phone or '—', name=name, district=row_district,
                                   category=category, outcome='invalid',
                                   lead_type=lead_type, confidence=confidence))
            continue

        stats['valid'] += 1
        if phone in seen_in_file:
            stats['duplicate_in_file'] += 1
            rows.append(PreviewRow(phone=phone, name=name, district=row_district,
                                   category=category, outcome='duplicate_in_file',
                                   lead_type=lead_type, confidence=confidence))
            continue
        seen_in_file.add(phone)

        if SuppressionEntry.objects.filter(phone_normalized=phone).exists():
            stats['suppressed'] += 1
            rows.append(PreviewRow(phone=phone, name=name, district=row_district,
                                   category=category, outcome='suppressed',
                                   lead_type=lead_type, confidence=confidence))
            continue

        existing_lead = MarketingLead.objects.filter(phone_normalized=phone).first()
        existing_user = find_user_by_phone(phone)

        if existing_user and (not existing_lead or existing_lead.status == MarketingLead.Status.EXISTING_USER):
            stats['existing_user'] += 1
            rows.append(PreviewRow(phone=phone, name=name, district=row_district,
                                   category=category, outcome='existing_user',
                                   lead_type=lead_type, confidence=confidence))
            continue

        if existing_lead:
            stats['already_lead'] += 1
            # sighting جدید روی commit اضافه می‌شود؛ هنوز eligible برای لیست است اگر cold/engaged
            if existing_lead.status in (
                MarketingLead.Status.REGISTERED,
                MarketingLead.Status.CUSTOMER,
                MarketingLead.Status.SUPPRESSED,
                MarketingLead.Status.EXISTING_USER,
            ):
                rows.append(PreviewRow(phone=phone, name=name, district=row_district,
                                       category=category, outcome='already_lead_blocked',
                                       lead_type=lead_type, confidence=confidence))
                continue
            stats['eligible'] += 1
            rows.append(PreviewRow(phone=phone, name=name, district=row_district,
                                   category=category, outcome='already_lead_update',
                                   lead_type=lead_type, confidence=confidence))
            continue

        if existing_user:
            stats['existing_user'] += 1
            rows.append(PreviewRow(phone=phone, name=name, district=row_district,
                                   category=category, outcome='existing_user',
                                   lead_type=lead_type, confidence=confidence))
            continue

        stats['eligible'] += 1
        rows.append(PreviewRow(phone=phone, name=name, district=row_district,
                               category=category, outcome='eligible',
                               lead_type=lead_type, confidence=confidence))

    scraped_at = meta.get('scraped_at') or meta.get('updated_at') or meta.get('started_at')
    return ImportPreview(
        rows=rows,
        stats=stats,
        file_hash=file_hash,
        duplicate_file=False,
        existing_batch_id=existing.pk if existing else None,
        metadata={
            'original_filename': filename,
            'city': city,
            'city_id': str(meta.get('city_id') or ''),
            'district': district,
            'district_id': str(meta.get('district_id') or ''),
            'listing_category': category,
            'scraped_at': scraped_at,
            'source_metadata': {
                k: meta.get(k)
                for k in (
                    'scanned_posts',
                    'total_consultants',
                    'with_phone_count',
                    'mode',
                    'requested_limit',
                )
                if k in meta
            },
        },
    )


def create_preview_batch(
    preview: ImportPreview,
    *,
    uploaded_by=None,
    raw_payload: Optional[dict] = None,
) -> LeadImportBatch:
    if preview.duplicate_file:
        raise LeadImportError('این فایل قبلاً commit شده است.', code='duplicate_file')

    scraped_at = None
    raw_scraped = (preview.metadata or {}).get('scraped_at')
    if raw_scraped:
        scraped_at = parse_datetime(str(raw_scraped)) if not isinstance(raw_scraped, datetime) else raw_scraped

    batch, _ = LeadImportBatch.objects.update_or_create(
        file_hash=preview.file_hash,
        defaults={
            'source': 'phone_detector',
            'original_filename': (preview.metadata or {}).get('original_filename') or '',
            'city': normalize_region_label((preview.metadata or {}).get('city') or ''),
            'city_id': (preview.metadata or {}).get('city_id') or '',
            'district': normalize_region_label((preview.metadata or {}).get('district') or ''),
            'district_id': (preview.metadata or {}).get('district_id') or '',
            'listing_category': normalize_region_label((preview.metadata or {}).get('listing_category') or ''),
            'scraped_at': scraped_at,
            'metadata': {
                **(preview.metadata or {}),
                'raw_preview_rows': len(preview.rows),
            },
            'preview_stats': preview.stats,
            'status': LeadImportBatch.Status.PREVIEW,
            'uploaded_by': uploaded_by,
        },
    )
    return batch


def normalize_region_label(text: str) -> str:
    """نرمال‌سازی نام شهر/منطقه برای ادغام (نیم‌فاصله، فاصله، ي/ك)."""
    if not text:
        return ''
    t = str(text).strip()
    t = t.replace('\u200c', '')  # ZWNJ
    t = t.replace('ك', 'ک').replace('ي', 'ی').replace('ة', 'ه')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


_PERSIAN_CHAR_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')


def looks_like_ascii_slug(text: str) -> bool:
    t = (text or '').strip()
    if not t or _PERSIAN_CHAR_RE.search(t):
        return False
    return bool(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', t, re.I))


def resolve_district_label(*, meta_district: str = '', item_district: str = '') -> str:
    """
    نام فارسی منطقه برای SMS/UI.
    metadata.district فارسی است؛ consultants[].district معمولاً slug انگلیسی.
    """
    meta = normalize_region_label(meta_district)
    item = (item_district or '').strip()
    if meta and looks_like_ascii_slug(item):
        return meta
    if item and not looks_like_ascii_slug(item):
        return normalize_region_label(item)
    if meta:
        return meta
    if item and looks_like_ascii_slug(item):
        return resolve_district_slug(item) or item
    return normalize_region_label(item) or item


_slug_to_district_cache: dict[str, str] | None = None


def _places_file_candidates() -> list:
    from pathlib import Path
    from django.conf import settings

    pd = (getattr(settings, 'PHONE_DETECTOR_DIR', None) or '').strip()
    candidates = []
    if pd:
        root = Path(pd).expanduser().resolve().parent
        candidates.append(root / 'config' / 'places-web.json')
        candidates.append(Path(pd).expanduser().resolve() / 'config' / 'places-web.json')
    base = Path(getattr(settings, 'BASE_DIR', Path.cwd()))
    candidates.extend([
        base.parent / 'config' / 'places-web.json',
        Path('/root/config/places-web.json'),
    ])
    return candidates


def _load_slug_to_district_map() -> dict[str, str]:
    global _slug_to_district_cache
    if _slug_to_district_cache is not None:
        return _slug_to_district_cache
    mapping: dict[str, str] = {}
    for path in _places_file_candidates():
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if str(item.get('type')) != '4':
                continue
            name = normalize_region_label(str(item.get('name') or ''))
            slug = str(item.get('slug') or '').strip().casefold()
            if name and slug:
                mapping[slug] = name
        break
    _slug_to_district_cache = mapping
    return mapping


def resolve_district_slug(slug: str) -> str:
    key = (slug or '').strip().casefold()
    if not key:
        return ''
    return _load_slug_to_district_map().get(key, '')


def display_district_for_lead(lead: MarketingLead) -> str:
    """برچسب فارسی منطقه برای {district} در پیامک."""
    raw = (lead.district or '').strip()
    if raw and not looks_like_ascii_slug(raw):
        return normalize_region_label(raw) or 'منطقه شما'

    batch = getattr(lead, 'first_batch', None)
    if batch is None and lead.first_batch_id:
        batch = LeadImportBatch.objects.filter(pk=lead.first_batch_id).only('district').first()
    if batch:
        batch_label = normalize_region_label(batch.district or '')
        if batch_label:
            return batch_label

    for entry in (lead.districts_json or []):
        label = normalize_region_label(str(entry or ''))
        if label and not looks_like_ascii_slug(label):
            return label

    if raw:
        resolved = resolve_district_slug(raw)
        if resolved:
            return resolved
        return raw

    city = normalize_region_label(lead.city or '')
    return city or 'منطقه شما'


def region_merge_key(city: str, district: str, category: str = '') -> str:
    parts = [
        normalize_region_label(city).casefold(),
        normalize_region_label(district).casefold(),
        normalize_region_label(category).casefold(),
    ]
    return '|'.join(parts)


def _list_slug(city: str, district: str, category: str = '') -> str:
    """اسلاگ پایدار منطقه‌ای — بدون batch_id تا فایل‌های همان منطقه ادغام شوند."""
    city_n = normalize_region_label(city) or 'city'
    district_n = normalize_region_label(district) or 'district'
    cat_n = normalize_region_label(category) or 'all'
    base = slugify(f'pd-{city_n}-{district_n}-{cat_n}', allow_unicode=True)
    base = re.sub(r'[^\w\-]+', '-', base, flags=re.UNICODE).strip('-')[:200]
    return base or 'pd-region'


def get_or_create_region_list(
    *,
    city: str,
    district: str,
    listing_category: str = '',
    batch: Optional[LeadImportBatch] = None,
) -> tuple[LeadList, bool]:
    """یک LeadList برای هر ترکیب شهر/منطقه/دسته."""
    slug = _list_slug(city, district, listing_category)
    city_n = normalize_region_label(city)
    district_n = normalize_region_label(district)
    cat_n = normalize_region_label(listing_category)
    list_name = ' · '.join(
        p for p in ('phone-detector', city_n or None, district_n or None, cat_n or None) if p
    )
    lead_list, created = LeadList.objects.get_or_create(
        slug=slug,
        defaults={
            'name': list_name,
            'source': 'phone_detector',
            'city': city_n,
            'district': district_n,
            'listing_category': cat_n,
            'tags': ['phone-detector', 'cold', city_n, district_n, 'region-merged'],
            'batch': batch,
        },
    )
    if not created:
        dirty = False
        if batch and not lead_list.batch_id:
            lead_list.batch = batch
            dirty = True
        # هم‌تراز کردن برچسب‌های نمایشی
        if city_n and lead_list.city != city_n:
            lead_list.city = city_n
            dirty = True
        if district_n and lead_list.district != district_n:
            lead_list.district = district_n
            dirty = True
        if dirty:
            lead_list.save()
    return lead_list, created


@transaction.atomic
def merge_duplicate_region_lists() -> dict:
    """
    لیست‌های تکراری همان منطقه را به لیست canonical (اسلاگ بدون batch_id) ادغام می‌کند.
    """
    from collections import defaultdict

    from accounts.models import LeadCampaign

    groups: dict[str, list[LeadList]] = defaultdict(list)
    for lst in LeadList.objects.filter(source='phone_detector').order_by('id'):
        key = region_merge_key(lst.city, lst.district, lst.listing_category)
        if key == '||':
            continue
        groups[key].append(lst)

    moved_members = 0
    deleted_lists = 0

    for _key, lists in groups.items():
        canonical_slug = _list_slug(lists[0].city, lists[0].district, lists[0].listing_category)
        primary = next((x for x in lists if x.slug == canonical_slug), None)
        if primary is None:
            primary = lists[0]
            conflict = LeadList.objects.filter(slug=canonical_slug).exclude(pk=primary.pk).first()
            if conflict:
                primary = conflict
                if primary not in lists:
                    lists.append(primary)
            else:
                primary.slug = canonical_slug
                primary.city = normalize_region_label(primary.city)
                primary.district = normalize_region_label(primary.district)
                primary.name = ' · '.join(
                    p for p in (
                        'phone-detector',
                        primary.city or None,
                        primary.district or None,
                        normalize_region_label(primary.listing_category) or None,
                    ) if p
                )
                if 'region-merged' not in (primary.tags or []):
                    primary.tags = list(primary.tags or []) + ['region-merged']
                primary.save()

        for other in list(LeadList.objects.filter(pk__in=[x.pk for x in lists])):
            if other.pk == primary.pk:
                continue
            for member in list(LeadListMember.objects.filter(lead_list=other)):
                _, created = LeadListMember.objects.get_or_create(
                    lead_list=primary,
                    lead_id=member.lead_id,
                )
                if created:
                    moved_members += 1
                member.delete()
            LeadCampaign.objects.filter(lead_list=other).update(lead_list=primary)
            for batch in LeadImportBatch.objects.filter(status=LeadImportBatch.Status.COMMITTED):
                stats = dict(batch.preview_stats or {})
                if stats.get('list_id') == other.pk:
                    stats['list_id'] = primary.pk
                    stats['merged_into_list_id'] = primary.pk
                    batch.preview_stats = stats
                    batch.save(update_fields=['preview_stats'])
            other.delete()
            deleted_lists += 1

    return {
        'moved_members': moved_members,
        'deleted_lists': deleted_lists,
        'region_groups': len(groups),
    }


def region_lists_with_batches(limit: int = 50) -> list[dict]:
    """خلاصه لیست‌های منطقه‌ای + تعداد بچ و عضو برای UI."""
    from django.db.models import Count

    rows = []
    lists = (
        LeadList.objects.filter(source='phone_detector')
        .annotate(member_count=Count('members', distinct=True))
        .order_by('city', 'district', '-updated_at')[:limit]
    )
    for lst in lists:
        batch_qs = LeadImportBatch.objects.filter(
            status=LeadImportBatch.Status.COMMITTED,
            city=lst.city,
            district=lst.district,
        )
        # همچنین با نرمال‌سازی نزدیک: همه بچ‌هایی که list_id در stats دارند
        linked = LeadImportBatch.objects.filter(
            status=LeadImportBatch.Status.COMMITTED,
            preview_stats__list_id=lst.pk,
        )
        batch_ids = set(batch_qs.values_list('id', flat=True)) | set(linked.values_list('id', flat=True))
        # نرمال‌سازی: اگر district با ZWNJ فرق دارد
        for b in LeadImportBatch.objects.filter(status=LeadImportBatch.Status.COMMITTED).only(
            'id', 'city', 'district', 'listing_category', 'preview_stats', 'original_filename', 'committed_at',
        ):
            if region_merge_key(b.city, b.district, b.listing_category or lst.listing_category) == region_merge_key(
                lst.city, lst.district, lst.listing_category,
            ):
                batch_ids.add(b.id)
        batches = list(
            LeadImportBatch.objects.filter(id__in=batch_ids).order_by('-committed_at', '-created_at')
        )
        rows.append({
            'list': lst,
            'member_count': lst.member_count,
            'batch_count': len(batches),
            'batches': batches,
            'latest_batch': batches[0] if batches else None,
        })
    # مرتب‌سازی: بیشتر عضو / جدیدتر
    rows.sort(key=lambda r: (-r['member_count'], -(r['latest_batch'].pk if r['latest_batch'] else 0)))
    return rows


@transaction.atomic
def commit_import_batch(batch_id: int, *, preview_rows: Optional[List[PreviewRow]] = None) -> dict:
    batch = LeadImportBatch.objects.select_for_update().get(pk=batch_id)
    if batch.status == LeadImportBatch.Status.COMMITTED:
        raise LeadImportError('این بچ قبلاً ثبت شده است.', code='already_committed')

    # اگر preview_rows نداریم از metadata کافی نیست — باید دوباره از فایل نباشد؛
    # caller باید rows را پاس دهد یا از preview ذخیره در session استفاده کند.
    if preview_rows is None:
        raise LeadImportError('ردیف‌های پیش‌نمایش برای commit لازم است.', code='missing_rows')

    created = 0
    updated = 0
    existing_user_marked = 0
    members_added = 0

    lead_list, list_created = get_or_create_region_list(
        city=batch.city,
        district=batch.district,
        listing_category=batch.listing_category,
        batch=batch,
    )

    now = timezone.now()
    for row in preview_rows:
        if row.outcome in ('invalid', 'duplicate_in_file', 'suppressed'):
            continue
        phone = row.phone
        user = find_user_by_phone(phone)
        district_label = resolve_district_label(meta_district=batch.district, item_district=row.district)

        if row.outcome == 'existing_user' or (user and row.outcome != 'already_lead_update'):
            lead, was_created = MarketingLead.objects.get_or_create(
                phone_normalized=phone,
                defaults={
                    'display_name': row.name,
                    'source': 'phone_detector',
                    'city': batch.city,
                    'district': district_label or batch.district,
                    'listing_category': batch.listing_category,
                    'lead_type': row.lead_type,
                    'classification_confidence': row.confidence,
                    'status': MarketingLead.Status.EXISTING_USER,
                    'matched_user': user,
                    'first_batch': batch,
                    'last_seen_at': now,
                    'districts_json': [district_label] if district_label else [],
                },
            )
            if not was_created:
                lead.status = MarketingLead.Status.EXISTING_USER
                lead.matched_user = user or lead.matched_user
                lead.sighting_count = (lead.sighting_count or 0) + 1
                lead.last_seen_at = now
                if district_label and district_label not in (lead.districts_json or []):
                    lead.districts_json = list(lead.districts_json or []) + [district_label]
                if district_label and (not lead.district or looks_like_ascii_slug(lead.district)):
                    lead.district = district_label
                lead.save()
                updated += 1
            else:
                created += 1
            existing_user_marked += 1
            try:
                from accounts.services.growth_journey import on_lead_imported
                on_lead_imported(lead)
            except Exception:
                pass
            continue

        if row.outcome in ('eligible', 'already_lead_update', 'already_lead_blocked'):
            if row.outcome == 'already_lead_blocked':
                lead = MarketingLead.objects.filter(phone_normalized=phone).first()
                if lead:
                    lead.sighting_count = (lead.sighting_count or 0) + 1
                    lead.last_seen_at = now
                    lead.save(update_fields=['sighting_count', 'last_seen_at', 'updated_at'])
                    updated += 1
                continue

            lead, was_created = MarketingLead.objects.get_or_create(
                phone_normalized=phone,
                defaults={
                    'display_name': row.name,
                    'source': 'phone_detector',
                    'city': batch.city,
                    'district': district_label or batch.district,
                    'listing_category': batch.listing_category,
                    'lead_type': row.lead_type,
                    'classification_confidence': row.confidence,
                    'status': MarketingLead.Status.COLD,
                    'matched_user': user,
                    'first_batch': batch,
                    'last_seen_at': now,
                    'districts_json': [district_label] if district_label else [],
                },
            )
            if was_created:
                created += 1
            else:
                lead.sighting_count = (lead.sighting_count or 0) + 1
                lead.last_seen_at = now
                if row.name and not lead.display_name:
                    lead.display_name = row.name
                if district_label and district_label not in (lead.districts_json or []):
                    lead.districts_json = list(lead.districts_json or []) + [district_label]
                if lead.status == MarketingLead.Status.COLD:
                    lead.city = lead.city or batch.city
                    if district_label and (not lead.district or looks_like_ascii_slug(lead.district)):
                        lead.district = district_label
                lead.save()
                updated += 1

            if lead.status in (MarketingLead.Status.COLD, MarketingLead.Status.ENGAGED):
                _, member_created = LeadListMember.objects.get_or_create(
                    lead_list=lead_list,
                    lead=lead,
                )
                if member_created:
                    members_added += 1
            try:
                from accounts.services.growth_journey import on_lead_imported
                on_lead_imported(lead)
            except Exception:
                pass

    batch.status = LeadImportBatch.Status.COMMITTED
    batch.committed_at = now
    # نرمال‌سازی geo روی خود batch برای گروه‌بندی بعدی
    city_n = normalize_region_label(batch.city)
    district_n = normalize_region_label(batch.district)
    if city_n != batch.city or district_n != batch.district:
        batch.city = city_n
        batch.district = district_n
    batch.preview_stats = {
        **(batch.preview_stats or {}),
        'committed_created': created,
        'committed_updated': updated,
        'existing_user_marked': existing_user_marked,
        'members_added': members_added,
        'list_id': lead_list.pk,
        'list_created': list_created,
        'region_merged': not list_created,
    }
    batch.save()

    # ادغام لیست‌های تکراری احتمالی همان منطقه (اسلاگ قدیمی)
    merge_duplicate_region_lists()

    return {
        'batch_id': batch.pk,
        'list_id': lead_list.pk,
        'list_created': list_created,
        'created': created,
        'updated': updated,
        'existing_user_marked': existing_user_marked,
        'members_added': members_added,
    }
