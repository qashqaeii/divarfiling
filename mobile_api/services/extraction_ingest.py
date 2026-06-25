"""دریافت و ذخیره استخراج سبک موبایل."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from django.db import transaction
from django.utils import timezone

from mobile_api.services.divar_flatten import flatten_divar_detail, is_roommate_ad
from workspace.models import Dataset, Listing, PriceHistory
from workspace.services.price_history import load_latest_snapshots, should_record_price

MAX_MOBILE_ITEMS = 100

CATEGORY_LABELS = {
    'apartment-rent': ('اجاره مسکونی', 'آپارتمان'),
    'house-villa-rent': ('اجاره مسکونی', 'خانه و ویلا'),
    'apartment-sell': ('فروش مسکونی', 'آپارتمان'),
    'house-villa-sell': ('فروش مسکونی', 'خانه و ویلا'),
    'office-rent': ('اجاره اداری', 'دفتر'),
    'office-sell': ('فروش اداری', 'دفتر'),
}


@dataclass
class IngestResult:
    dataset: Dataset
    ingested_count: int
    skipped_count: int


def ingest_mobile_extraction(user, payload: Dict[str, Any]) -> IngestResult:
    items = payload.get('items') or []
    if len(items) > MAX_MOBILE_ITEMS:
        raise ValueError(f'حداکثر {MAX_MOBILE_ITEMS} آگهی مجاز است.')

    filters = payload.get('filters') or {}
    category = str(filters.get('category') or 'apartment-rent')
    tx_type, subcat = CATEGORY_LABELS.get(category, ('استخراج موبایل', category))
    city = str(filters.get('city_id') or '')
    max_items = int(filters.get('max_items') or len(items))

    now = timezone.now()
    name = f'موبایل — {subcat} — {now.strftime("%Y/%m/%d %H:%M")}'

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
        if is_roommate_ad(flat):
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
            original_filename='mobile_extraction.json',
            file_format='json',
            file_size=0,
            row_count=0,
            column_count=0,
            columns=[],
            transaction_type=tx_type,
            subcategory=subcat,
            city=city,
            district='',
            metadata={
                'source': 'mobile',
                'mobile_extraction': True,
                'filters': filters,
                'started_at': payload.get('started_at'),
                'finished_at': payload.get('finished_at'),
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
                city=flat.get('city') or '',
                latitude=flat.get('latitude'),
                longitude=flat.get('longitude'),
                business_type=flat.get('business_type') or '',
                description=flat.get('description') or '',
                link=flat.get('link') or '',
                images=flat.get('images') or [],
                data=flat.get('data') or flat,
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
