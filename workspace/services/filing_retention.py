"""نگهداری موقت آگهی‌های فایلینگ — حذف بر اساس سن، بدون سرکوب کاربر."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from workspace.models import Listing

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 31
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 3650
DEFAULT_BATCH_SIZE = 500


def filing_listing_retention_days() -> int:
    raw = getattr(settings, 'FILING_LISTING_RETENTION_DAYS', DEFAULT_RETENTION_DAYS)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = DEFAULT_RETENTION_DAYS
    return max(MIN_RETENTION_DAYS, min(MAX_RETENTION_DAYS, days))


def listing_retention_anchor(listing: Listing):
    """
    تاریخ مبنای retention:
    1. published_at — زمان انتشار/ایجاد آگهی در دیوار (در صورت وجود)
    2. created_at — زمان اولین ذخیره در فایلینگ
    """
    if listing.published_at:
        return listing.published_at
    return listing.created_at


def stale_filing_listings_qs(*, as_of=None) -> QuerySet:
    """آگهی‌های فایلینگ قدیمی‌تر از آستانه — فقط دیتاست‌های فعال."""
    as_of = as_of or timezone.now()
    cutoff = as_of - timedelta(days=filing_listing_retention_days())
    return Listing.objects.filter(dataset__is_active=True).filter(
        Q(published_at__lt=cutoff)
        | Q(published_at__isnull=True, created_at__lt=cutoff),
    )


def purge_stale_filing_listings(*, dry_run: bool = False, batch_size: int = DEFAULT_BATCH_SIZE) -> dict:
    """
    حذف آگهی‌های قدیمی فایلینگ.
    CRMProperty / سرکوب کاربر / ListingMeta دست نخورده.
    ListingPublicShare با CASCADE حذف می‌شود (نمایش موقت فایلینگ).
    """
    from workspace.models import Dataset

    batch_size = max(1, min(batch_size, 5000))
    stats = {
        'eligible': 0,
        'deleted': 0,
        'affected_datasets': 0,
        'dry_run': dry_run,
        'retention_days': filing_listing_retention_days(),
        'batch_size': batch_size,
    }
    stats['eligible'] = stale_filing_listings_qs().count()
    if dry_run or stats['eligible'] == 0:
        return stats

    affected_dataset_ids: set = set()
    deleted_listings = 0

    with transaction.atomic():
        while True:
            batch_ids = list(
                stale_filing_listings_qs()
                .order_by('pk')
                .values_list('pk', flat=True)[:batch_size]
            )
            if not batch_ids:
                break
            for ds_id in Listing.objects.filter(pk__in=batch_ids).values_list('dataset_id', flat=True):
                affected_dataset_ids.add(ds_id)
            deleted, detail = Listing.objects.filter(pk__in=batch_ids).delete()
            deleted_listings += detail.get('workspace.Listing', deleted)

        for ds_id in affected_dataset_ids:
            Dataset.objects.filter(pk=ds_id).update(
                row_count=Listing.objects.filter(dataset_id=ds_id).count(),
            )

    stats['deleted'] = deleted_listings
    stats['affected_datasets'] = len(affected_dataset_ids)
    logger.info(
        'purge_stale_filing_listings deleted=%s eligible=%s datasets=%s retention_days=%s',
        stats['deleted'], stats['eligible'], stats['affected_datasets'], stats['retention_days'],
    )
    return stats
