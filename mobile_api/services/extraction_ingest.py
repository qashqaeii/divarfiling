"""دریافت و ذخیره استخراج سبک موبایل — همان مسیر import اکسل."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd
from django.db import transaction
from django.utils import timezone

from mobile_api.services.divar_flatten import items_to_export_records
from workspace.models import Dataset, Listing, PriceHistory
from workspace.services.columns import detect_metadata, row_to_listing_fields
from workspace.services.folder_import import build_dataset_name, build_file_identity
from workspace.services.importer import (
    _listing_from_fields,
    _update_listing_from_fields,
    find_existing_dataset,
)
from workspace.services.price_history import load_latest_snapshots, should_record_price

MAX_MOBILE_ITEMS = 100
INGEST_VERSION = 4
logger = logging.getLogger(__name__)

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
        base = hint.split('_')[0] if re.match(r'^.+_\d{8}_\d{6}$', hint) else hint
        base = base if not base.endswith(('.json', '.xlsx', '.xls')) else os.path.splitext(base)[0]
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

    export_records, skipped = items_to_export_records(
        items,
        category,
        advertiser_filter=advertiser_filter,
        max_items=max_items,
    )
    if not export_records:
        raise ValueError('آگهی معتبری برای ذخیره یافت نشد.')

    # همان DataFrame و row_to_listing_fields که import اکسل/JSON ویندوز استفاده می‌کند
    df = pd.DataFrame(export_records)
    df = df.where(pd.notna(df), None)
    file_meta = detect_metadata(df)
    columns = list(df.columns.astype(str))

    original_filename = _resolve_original_filename(filters)
    path_info = {
        'city': city or file_meta.get('city', ''),
        'district': district or file_meta.get('district', ''),
        'transaction_type': tx_type or file_meta.get('transaction_type', ''),
        'subcategory': subcat,
        'tx_slug': os.path.splitext(original_filename)[0],
        'filename': original_filename,
        'province': str(filters.get('province_name') or '').strip(),
    }
    name = _resolve_dataset_display_name(path_info, original_filename)
    file_identity = build_file_identity(path_info, original_filename)

    now = timezone.now()
    tokens = [
        str(row_to_listing_fields(df.iloc[i], df).get('token') or '').strip()
        for i in range(len(df))
    ]
    tokens = [t for t in tokens if t]
    price_cache = load_latest_snapshots(user, tokens)

    with transaction.atomic():
        existing, _reactivating = find_existing_dataset(user, original_filename, path_info)
        metadata = {
            'source': 'mobile',
            'mobile_extraction': True,
            'ingest_version': INGEST_VERSION,
            'source_client': str(filters.get('source_client') or 'android_light'),
            'filters': filters,
            'started_at': payload.get('started_at'),
            'finished_at': payload.get('finished_at'),
            'province': path_info.get('province', ''),
            'transaction_type': path_info['transaction_type'],
            'subcategory': subcat,
            'city': path_info['city'],
            'district': path_info['district'],
            'file_identity': file_identity,
        }

        if existing:
            dataset = existing
            dataset.metadata = {**(dataset.metadata or {}), **metadata}
            dataset.last_opened_at = now
            dataset.is_active = True
            dataset.column_count = len(columns)
            merged_columns = list(dict.fromkeys(list((dataset.columns or [])) + columns))
            dataset.columns = merged_columns
            if path_info['city']:
                dataset.city = path_info['city']
            if path_info['district']:
                dataset.district = path_info['district']
            if tx_type:
                dataset.transaction_type = tx_type
            if subcat:
                dataset.subcategory = subcat
            existing_by_token = {
                listing.token: listing
                for listing in Listing.objects.filter(dataset=dataset)
            }
        else:
            dataset = Dataset(
                user=user,
                name=name,
                original_filename=original_filename,
                file_format='json',
                file_size=0,
                row_count=0,
                column_count=len(columns),
                columns=columns,
                transaction_type=path_info['transaction_type'],
                subcategory=subcat,
                city=path_info['city'],
                district=path_info['district'],
                metadata=metadata,
                last_opened_at=now,
            )
            existing_by_token = {}

        listings_to_create: List[Listing] = []
        listings_to_update: List[Listing] = []
        price_records: List[PriceHistory] = []
        seen_tokens: set = set()
        duplicate_skipped = 0

        for idx in range(len(df)):
            fields = row_to_listing_fields(df.iloc[idx], df)
            token = fields['token']
            if token in seen_tokens:
                duplicate_skipped += 1
                continue
            seen_tokens.add(token)

            if token in existing_by_token:
                listing = existing_by_token[token]
                if _update_listing_from_fields(listing, fields):
                    listings_to_update.append(listing)
                else:
                    duplicate_skipped += 1
            else:
                listings_to_create.append(_listing_from_fields(dataset, fields))

            price = fields['price']
            deposit = fields['deposit']
            rent = fields['rent']
            if should_record_price(price_cache, token, price, deposit, rent):
                price_records.append(PriceHistory(
                    user=user,
                    token=token,
                    price=price,
                    deposit=deposit,
                    rent=rent,
                ))

        if not existing:
            dataset.save()

        if listings_to_create:
            Listing.objects.bulk_create(listings_to_create, batch_size=200)
        if listings_to_update:
            Listing.objects.bulk_update(
                listings_to_update,
                [
                    'title', 'price', 'deposit', 'rent', 'area', 'rooms',
                    'neighborhood', 'city', 'latitude', 'longitude',
                    'business_type', 'description', 'link', 'images',
                    'published_at', 'expires_at', 'data',
                ],
                batch_size=200,
            )
        if price_records:
            PriceHistory.objects.bulk_create(price_records, batch_size=200)

        dataset.row_count = Listing.objects.filter(dataset=dataset).count()
        dataset.save(update_fields=[
            'row_count', 'metadata', 'last_opened_at', 'is_active',
            'city', 'district', 'columns', 'column_count',
            'transaction_type', 'subcategory',
        ])

    ingested_count = len(seen_tokens)
    result = IngestResult(
        dataset=dataset,
        ingested_count=ingested_count,
        skipped_count=skipped + duplicate_skipped,
    )
    try:
        from mobile_api.services.notification_service import notify_extract_complete
        notify_extract_complete(user, str(dataset.pk), dataset.name, ingested_count)
    except Exception:
        logger.exception('failed to send extract notification')
    return result


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

