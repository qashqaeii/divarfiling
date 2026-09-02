"""نگهداری موقت آگهی‌های فایلینگ — حذف بر اساس سن، بدون سرکوب کاربر."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from django.utils import timezone

from workspace.constants import FILING_LISTING_RETENTION_DAYS_DEFAULT
from workspace.models import Listing, ListingMeta, ListingPublicShare

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = FILING_LISTING_RETENTION_DAYS_DEFAULT
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 3650
DEFAULT_BATCH_SIZE = 500

# برچسب‌های فایلینگ که نشان‌دهنده تعامل فعال مشاور با آگهی هستند.
WORKFLOW_RETENTION_TAGS = ('تماس', 'بازدید', 'علاقه‌مند')


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
    """آگهی‌های فایلینگ قدیمی‌تر از آستانه — فقط دیتاست‌های فعال (بدون exclusion)."""
    as_of = as_of or timezone.now()
    cutoff = as_of - timedelta(days=filing_listing_retention_days())
    return Listing.objects.filter(dataset__is_active=True).filter(
        Q(published_at__lt=cutoff)
        | Q(published_at__isnull=True, created_at__lt=cutoff),
    )


def _active_public_share_exists() -> Exists:
    return Exists(
        ListingPublicShare.objects.filter(
            listing_id=OuterRef('pk'),
            is_active=True,
        ),
    )


def _owner_favorite_meta_exists() -> Exists:
    return Exists(
        ListingMeta.objects.filter(
            user_id=OuterRef('dataset__user_id'),
            token=OuterRef('token'),
            is_favorite=True,
        ),
    )


def _owner_meaningful_note_meta_exists() -> Exists:
    return Exists(
        ListingMeta.objects.filter(
            user_id=OuterRef('dataset__user_id'),
            token=OuterRef('token'),
        ).exclude(Q(note='') | Q(note__isnull=True)),
    )


def _owner_workflow_tag_meta_exists() -> Exists:
    return Exists(
        ListingMeta.objects.filter(
            user_id=OuterRef('dataset__user_id'),
            token=OuterRef('token'),
            tag__in=WORKFLOW_RETENTION_TAGS,
        ),
    )


def _customer_listing_relation_exists() -> Exists:
    from workspace.models import CustomerListing

    return Exists(
        CustomerListing.objects.filter(
            token=OuterRef('token'),
            customer__user_id=OuterRef('dataset__user_id'),
        ),
    )


def _listing_retention_protection_q() -> Q:
    """هر شرطی که آگهی را از retention خودکار معاف می‌کند."""
    return (
        Q(Exists(
            ListingPublicShare.objects.filter(
                listing_id=OuterRef('pk'),
                is_active=True,
            ),
        ))
        | Q(Exists(
            ListingMeta.objects.filter(
                user_id=OuterRef('dataset__user_id'),
                token=OuterRef('token'),
                is_favorite=True,
            ),
        ))
        | Q(Exists(
            ListingMeta.objects.filter(
                user_id=OuterRef('dataset__user_id'),
                token=OuterRef('token'),
            ).exclude(Q(note='') | Q(note__isnull=True)),
        ))
        | Q(Exists(
            ListingMeta.objects.filter(
                user_id=OuterRef('dataset__user_id'),
                token=OuterRef('token'),
                tag__in=WORKFLOW_RETENTION_TAGS,
            ),
        ))
        | Q(_customer_listing_relation_exists())
    )


def purge_eligible_filing_listings_qs(*, as_of=None) -> QuerySet:
    """آگهی‌های واجد شرایط حذف پس از اعمال exclusionهای تعامل کاربر."""
    return stale_filing_listings_qs(as_of=as_of).exclude(_listing_retention_protection_q())


def _sync_dataset_row_counts(dataset_ids: set) -> None:
    """همگام‌سازی row_count فقط برای datasetهای تحت تأثیر — بدون N+1."""
    from workspace.models import Dataset

    if not dataset_ids:
        return
    count_map = {
        row['dataset_id']: row['c']
        for row in Listing.objects.filter(dataset_id__in=dataset_ids)
        .values('dataset_id')
        .annotate(c=Count('pk'))
    }
    datasets = list(Dataset.objects.filter(pk__in=dataset_ids))
    for ds in datasets:
        ds.row_count = count_map.get(ds.pk, 0)
    if datasets:
        Dataset.objects.bulk_update(datasets, ['row_count'])


def _delete_listing_batch(batch_ids: list) -> tuple[int, dict]:
    return Listing.objects.filter(pk__in=batch_ids).delete()


def _owner_any_meta_exists() -> Exists:
    return Exists(
        ListingMeta.objects.filter(
            user_id=OuterRef('dataset__user_id'),
            token=OuterRef('token'),
        ),
    )


def build_retention_breakdown(*, as_of=None) -> dict:
    """
    شمارش dry-run با breakdown — category counts ممکن است overlap داشته باشند.
    unique_protected و final_eligible بدون double-count هستند.
    """
    base = stale_filing_listings_qs(as_of=as_of)
    share_q = _active_public_share_exists()
    fav_q = _owner_favorite_meta_exists()
    note_q = _owner_meaningful_note_meta_exists()
    tag_q = _owner_workflow_tag_meta_exists()
    customer_q = _customer_listing_relation_exists()

    protected_q = _listing_retention_protection_q()
    unique_protected_qs = base.filter(protected_q)
    final_qs = base.exclude(protected_q)

    return {
        'retention_days': filing_listing_retention_days(),
        'base_age_eligible': base.count(),
        'protected_public_share': base.filter(share_q).count(),
        'protected_favorite': base.filter(fav_q).count(),
        'protected_note': base.filter(note_q).count(),
        'protected_workflow_tag': base.filter(tag_q).count(),
        'protected_customer_relation': base.filter(customer_q).count(),
        'unique_protected': unique_protected_qs.count(),
        'final_eligible': final_qs.count(),
    }


def build_listing_meta_audit_counts(*, as_of=None) -> dict:
    """
    شمارش read-only ListingMeta روی base_age_eligible — جفت دقیق (user, token).
    برای audit production؛ از filter(user_id__in=..., token__in=...) استفاده نکنید.
    """
    base = stale_filing_listings_qs(as_of=as_of)
    return {
        'any_meta': base.filter(_owner_any_meta_exists()).count(),
        'favorite': base.filter(_owner_favorite_meta_exists()).count(),
        'note': base.filter(_owner_meaningful_note_meta_exists()).count(),
        'workflow_tag': base.filter(_owner_workflow_tag_meta_exists()).count(),
        'rejected_tag': base.filter(Exists(
            ListingMeta.objects.filter(
                user_id=OuterRef('dataset__user_id'),
                token=OuterRef('token'),
                tag='رد',
            ),
        )).count(),
    }


def purge_stale_filing_listings(
    *,
    dry_run: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_delete: int | None = None,
) -> dict:
    """
    حذف آگهی‌های قدیمی فایلینگ.
    CRMProperty / سرکوب کاربر / ListingMeta / CustomerListing دست نخورده.
    آگهی با share فعال، علاقه‌مند، یادداشت، برچسب workflow، یا CustomerListing حذف نمی‌شود.
    """
    if max_delete is not None and max_delete < 0:
        raise ValueError('max_delete must be non-negative')

    batch_size = max(1, min(batch_size, 5000))
    breakdown = build_retention_breakdown()
    stats = {
        **breakdown,
        'eligible': breakdown['final_eligible'],
        'deleted': 0,
        'affected_datasets': 0,
        'batches': 0,
        'remaining_eligible': breakdown['final_eligible'],
        'dry_run': dry_run,
        'batch_size': batch_size,
        'max_delete': max_delete,
    }
    if dry_run or stats['eligible'] == 0 or max_delete == 0:
        return stats

    affected_dataset_ids: set = set()
    deleted_listings = 0
    batches = 0
    delete_quota = max_delete

    while True:
        if delete_quota is not None and delete_quota <= 0:
            break

        fetch_size = batch_size
        if delete_quota is not None:
            fetch_size = min(batch_size, delete_quota)

        batch_ids = list(
            purge_eligible_filing_listings_qs()
            .order_by('pk')
            .values_list('pk', flat=True)[:fetch_size]
        )
        if not batch_ids:
            break

        with transaction.atomic():
            batch_dataset_ids = set(
                Listing.objects.filter(pk__in=batch_ids).values_list('dataset_id', flat=True),
            )
            deleted, detail = _delete_listing_batch(batch_ids)
            batch_deleted = detail.get('workspace.Listing', deleted)
            deleted_listings += batch_deleted
            affected_dataset_ids.update(batch_dataset_ids)
            _sync_dataset_row_counts(batch_dataset_ids)

        if delete_quota is not None:
            delete_quota -= batch_deleted

        batches += 1
        logger.info(
            'purge_stale_filing_listings batch=%s deleted_in_batch=%s total_deleted=%s',
            batches,
            batch_deleted,
            deleted_listings,
        )

    stats['deleted'] = deleted_listings
    stats['affected_datasets'] = len(affected_dataset_ids)
    stats['batches'] = batches
    stats['remaining_eligible'] = purge_eligible_filing_listings_qs().count()
    logger.info(
        'purge_stale_filing_listings deleted=%s eligible=%s datasets=%s batches=%s retention_days=%s',
        stats['deleted'],
        stats['eligible'],
        stats['affected_datasets'],
        stats['batches'],
        stats['retention_days'],
    )
    return stats
