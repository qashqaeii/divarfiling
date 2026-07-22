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
        row_district = str(item.get('district') or district or '')
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
            'city': (preview.metadata or {}).get('city') or '',
            'city_id': (preview.metadata or {}).get('city_id') or '',
            'district': (preview.metadata or {}).get('district') or '',
            'district_id': (preview.metadata or {}).get('district_id') or '',
            'listing_category': (preview.metadata or {}).get('listing_category') or '',
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


def _list_slug(city: str, district: str, category: str, batch_id: int) -> str:
    base = slugify(f'pd-{city}-{district}-{category}-{batch_id}', allow_unicode=True)
    base = re.sub(r'[^\w\-]+', '-', base, flags=re.UNICODE).strip('-')[:180]
    return base or f'pd-batch-{batch_id}'


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

    list_name = ' · '.join(
        p for p in (
            'phone-detector',
            batch.city or None,
            batch.district or None,
            batch.listing_category or None,
            f'batch-{batch.pk}',
        ) if p
    )
    lead_list, _ = LeadList.objects.get_or_create(
        slug=_list_slug(batch.city, batch.district, batch.listing_category, batch.pk),
        defaults={
            'name': list_name,
            'source': 'phone_detector',
            'city': batch.city,
            'district': batch.district,
            'listing_category': batch.listing_category,
            'tags': ['phone-detector', 'cold', batch.city, batch.district],
            'batch': batch,
        },
    )

    now = timezone.now()
    for row in preview_rows:
        if row.outcome in ('invalid', 'duplicate_in_file', 'suppressed'):
            continue
        phone = row.phone
        user = find_user_by_phone(phone)

        if row.outcome == 'existing_user' or (user and row.outcome != 'already_lead_update'):
            lead, was_created = MarketingLead.objects.get_or_create(
                phone_normalized=phone,
                defaults={
                    'display_name': row.name,
                    'source': 'phone_detector',
                    'city': batch.city,
                    'district': row.district or batch.district,
                    'listing_category': batch.listing_category,
                    'lead_type': row.lead_type,
                    'classification_confidence': row.confidence,
                    'status': MarketingLead.Status.EXISTING_USER,
                    'matched_user': user,
                    'first_batch': batch,
                    'last_seen_at': now,
                    'districts_json': [row.district] if row.district else [],
                },
            )
            if not was_created:
                lead.status = MarketingLead.Status.EXISTING_USER
                lead.matched_user = user or lead.matched_user
                lead.sighting_count = (lead.sighting_count or 0) + 1
                lead.last_seen_at = now
                if row.district and row.district not in (lead.districts_json or []):
                    lead.districts_json = list(lead.districts_json or []) + [row.district]
                lead.save()
                updated += 1
            else:
                created += 1
            existing_user_marked += 1
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
                    'district': row.district or batch.district,
                    'listing_category': batch.listing_category,
                    'lead_type': row.lead_type,
                    'classification_confidence': row.confidence,
                    'status': MarketingLead.Status.COLD,
                    'matched_user': user,
                    'first_batch': batch,
                    'last_seen_at': now,
                    'districts_json': [row.district] if row.district else [],
                },
            )
            if was_created:
                created += 1
            else:
                lead.sighting_count = (lead.sighting_count or 0) + 1
                lead.last_seen_at = now
                if row.name and not lead.display_name:
                    lead.display_name = row.name
                if row.district and row.district not in (lead.districts_json or []):
                    lead.districts_json = list(lead.districts_json or []) + [row.district]
                if lead.status == MarketingLead.Status.COLD:
                    lead.city = lead.city or batch.city
                    lead.district = lead.district or row.district or batch.district
                lead.save()
                updated += 1

            if lead.status in (MarketingLead.Status.COLD, MarketingLead.Status.ENGAGED):
                _, member_created = LeadListMember.objects.get_or_create(
                    lead_list=lead_list,
                    lead=lead,
                )
                if member_created:
                    members_added += 1

    batch.status = LeadImportBatch.Status.COMMITTED
    batch.committed_at = now
    batch.preview_stats = {
        **(batch.preview_stats or {}),
        'committed_created': created,
        'committed_updated': updated,
        'existing_user_marked': existing_user_marked,
        'members_added': members_added,
        'list_id': lead_list.pk,
    }
    batch.save()

    return {
        'batch_id': batch.pk,
        'list_id': lead_list.pk,
        'created': created,
        'updated': updated,
        'existing_user_marked': existing_user_marked,
        'members_added': members_added,
    }
