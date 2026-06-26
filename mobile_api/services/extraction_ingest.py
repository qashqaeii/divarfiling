"""دریافت و ذخیره استخراج سبک موبایل."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

from django.db import transaction
from django.utils import timezone

from mobile_api.services.divar_flatten import (
    flatten_divar_detail,
    is_consultant_ad,
    is_roommate_ad,
)
from workspace.models import Dataset, Listing, PriceHistory
from workspace.services.folder_import import build_dataset_name
from workspace.services.price_history import load_latest_snapshots, should_record_price

MAX_MOBILE_ITEMS = 100
INGEST_VERSION = 2

CATEGORY_LABELS = {
    'apartment-rent': ('اجاره مسکونی', 'آپارتمان'),
    'house-villa-rent': ('اجاره مسکونی', 'خانه و ویلا'),
    'residential-sell': ('فروش مسکونی', 'آپارتمان'),
    'house-villa-sell': ('فروش مسکونی', 'خانه و ویلا'),
    'plot-old': ('فروش مسکونی', 'کلنگی'),
    'office-rent': ('اجاره اداری و تجاری', 'دفتر کار'),
    'shop-rent': ('اجاره اداری و تجاری', 'مغازه و غرفه'),
    'industry-agriculture-business-rent': ('اجاره اداری و تجاری', 'صنعتی و تجاری'),
    'office-sell': ('فروش اداری و تجاری', 'دفتر کار'),
    'shop-sell': ('فروش اداری و تجاری', 'مغازه و غرفه'),
    'industry-agriculture-business-sell': ('فروش اداری و تجاری', 'صنعتی و تجاری'),
    'real-estate-services': ('پروژه‌های ساخت‌وساز', 'پروژه'),
    'apartment-sell': ('فروش مسکونی', 'آپارتمان'),
}


@dataclass
class IngestResult:
    dataset: Dataset
    ingested_count: int
    skipped_count: int


def _resolve_tx_subcategory(filters: Dict[str, Any], category: str) -> tuple[str, str]:
    tx_type = str(filters.get('transaction_type_label') or '').strip()
    subcat = str(filters.get('category_label') or '').strip()
    if tx_type and subcat:
        return tx_type, subcat
    fallback_tx, fallback_sub = CATEGORY_LABELS.get(category, ('استخراج موبایل', category))
    return tx_type or fallback_tx, subcat or fallback_sub


def _resolve_location(filters: Dict[str, Any]) -> tuple[str, str]:
    city = str(filters.get('city_name') or '').strip()
    if not city:
        city_id = str(filters.get('city_id') or '').strip()
        city = city_id if city_id and not city_id.isdigit() else ''

    district_names = filters.get('district_names') or []
    district = ''
    if isinstance(district_names, list) and district_names:
        district = str(district_names[0] or '').strip()
    return city, district


def _resolve_original_filename(filters: Dict[str, Any]) -> str:
    hint = str(filters.get('output_name_hint') or '').strip()
    if hint:
        base = hint if not hint.endswith(('.json', '.xlsx', '.xls')) else os.path.splitext(hint)[0]
        return f'{base}.json'
    return 'mobile_extraction.json'


def _resolve_dataset_display_name(path_info: Dict[str, Any], original_filename: str) -> str:
    built = build_dataset_name(path_info, original_filename)
    if built and built != os.path.splitext(os.path.basename(original_filename))[0]:
        return built
    parts = []
    if path_info.get('district'):
        parts.append(path_info['district'])
    elif path_info.get('city'):
        parts.append(path_info['city'])
    if path_info.get('subcategory'):
        parts.append(path_info['subcategory'])
    return ' — '.join(parts) if parts else built


def ingest_mobile_extraction(user, payload: Dict[str, Any]) -> IngestResult:
    items = payload.get('items') or []
    if len(items) > MAX_MOBILE_ITEMS:
        raise ValueError(f'حداکثر {MAX_MOBILE_ITEMS} آگهی مجاز است.')

    filters = payload.get('filters') or {}
    category = str(filters.get('category') or 'apartment-rent')
    tx_type, subcat = _resolve_tx_subcategory(filters, category)
    city, district = _resolve_location(filters)
    advertiser_filter = str(filters.get('advertiser_filter') or 'all').strip().lower()
    max_items = int(filters.get('max_items') or len(items))

    original_filename = _resolve_original_filename(filters)
    path_info = {
        'city': city,
        'district': district,
        'transaction_type': tx_type,
        'subcategory': subcat,
    }
    name = _resolve_dataset_display_name(path_info, original_filename)

    now = timezone.now()

    flats: List[Dict[str, Any]] = []
    skipped = 0
    for item in items:
        token = str(item.get('token') or '').strip()
        raw = item.get('raw') or item
        if isinstance(raw, dict) and 'sections' in raw:
            flat = flatten_divar_detail(raw, token)
        else:
            flat = flatten_divar_detail(raw if isinstance(raw, dict) else {}, token)
        if not flat.get('token'):
            skipped += 1
            continue
        if is_roommate_ad(flat, category):
            skipped += 1
            continue
        if advertiser_filter == 'personal' and is_consultant_ad(flat):
            skipped += 1
            continue
        if advertiser_filter == 'consultant' and not is_consultant_ad(flat):
            skipped += 1
            continue
        flats.append(flat)
        if len(flats) >= max_items:
            break

    if not flats:
        raise ValueError('آگهی معتبری برای ذخیره یافت نشد.')

    tokens = [f['token'] for f in flats]
    price_cache = load_latest_snapshots(user, tokens)

    with transaction.atomic():
        dataset = Dataset.objects.create(
            user=user,
            name=name,
            original_filename=original_filename,
            file_format='json',
            file_size=0,
            row_count=0,
            column_count=0,
            columns=[],
            transaction_type=tx_type,
            subcategory=subcat,
            city=city,
            district=district,
            metadata={
                'source': 'mobile',
                'mobile_extraction': True,
                'ingest_version': INGEST_VERSION,
                'source_client': str(filters.get('source_client') or 'android_light'),
                'filters': filters,
                'started_at': payload.get('started_at'),
                'finished_at': payload.get('finished_at'),
                'province': filters.get('province_name') or '',
                'transaction_type': tx_type,
                'subcategory': subcat,
                'city': city,
                'district': district,
            },
            last_opened_at=now,
        )

        listings: List[Listing] = []
        price_records: List[PriceHistory] = []

        for flat in flats:
            token = flat['token']
            listing = Listing(
                dataset=dataset,
                token=token,
                title=flat.get('title') or '',
                price=flat.get('price'),
                deposit=flat.get('deposit'),
                rent=flat.get('rent'),
                area=flat.get('area'),
                rooms=str(flat.get('rooms') or ''),
                neighborhood=flat.get('district') or flat.get('neighborhood') or '',
                city=flat.get('city') or city,
                latitude=flat.get('latitude'),
                longitude=flat.get('longitude'),
                business_type=flat.get('business_type') or '',
                description=flat.get('description') or '',
                link=flat.get('link') or '',
                images=flat.get('images') or [],
                data=flat.get('data') or {},
            )
            listings.append(listing)

            if should_record_price(
                price_cache,
                token,
                listing.price,
                listing.deposit,
                listing.rent,
            ):
                price_records.append(PriceHistory(
                    user=user,
                    token=token,
                    price=listing.price,
                    deposit=listing.deposit,
                    rent=listing.rent,
                ))

        Listing.objects.bulk_create(listings, batch_size=200)
        if price_records:
            PriceHistory.objects.bulk_create(price_records, batch_size=200)

        dataset.row_count = len(listings)
        dataset.save(update_fields=['row_count'])

    return IngestResult(dataset=dataset, ingested_count=len(listings), skipped_count=skipped)


def extraction_limits_payload(user) -> Dict[str, Any]:
    from django.utils import timezone as tz
    today_start = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
    count_today = Dataset.objects.filter(
        user=user,
        metadata__mobile_extraction=True,
        created_at__gte=today_start,
    ).count()
    return {
        'max_items': MAX_MOBILE_ITEMS,
        'max_concurrent_hint': 2,
        'extractions_today': count_today,
        'extractions_daily_limit': 10,
    }
