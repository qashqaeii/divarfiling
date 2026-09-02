"""نگهداری موقت آگهی‌های فایلینگ — inactivity + پاک‌سازی ماهانه."""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from django.utils import timezone

from workspace.constants import FILING_LISTING_RETENTION_DAYS_DEFAULT, WORKFLOW_RETENTION_TAGS
from workspace.models import Listing, ListingMeta, ListingPublicShare
from workspace.services.listing_activity import get_listing_activity_map
from workspace.services.listing_personal_status import DIVAR_SOURCE_PLATFORM
from workspace.services.listing_retention_calendar import (
    current_month_cleanup_datetime,
    filing_listing_retention_days,
    is_monthly_cleanup_day,
    retention_feature_deployed_at,
)
from workspace.services.listing_retention_status import (
    _customer_listing_relation_exists,
    inactive_listings_base_qs,
    is_listing_purge_due,
)

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = FILING_LISTING_RETENTION_DAYS_DEFAULT
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 3650
DEFAULT_BATCH_SIZE = 500


def stale_filing_listings_qs(*, as_of=None) -> QuerySet:
    """Listingهای inactive — بر اساس effective_last_activity (نه published_at)."""
    return inactive_listings_base_qs(as_of=as_of)


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


def _listing_retention_protection_q() -> Q:
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
    )  # Exists wrapped in Q for OR-combination


def _purge_due_listing_ids(
    *,
    as_of=None,
    limit: int | None = None,
) -> list:
    as_of = as_of or timezone.now()
    cleanup_at = current_month_cleanup_datetime(as_of)
    base = stale_filing_listings_qs(as_of=as_of).exclude(_listing_retention_protection_q()).order_by('pk')
    tokens = list(base.values_list('token', flat=True).distinct())
    user_tokens: dict[int, set[str]] = {}
    for user_id, token in base.values_list('dataset__user_id', 'token'):
        user_tokens.setdefault(user_id, set()).add(token)

    activity_by_user: dict[int, dict[str, timezone.datetime]] = {}
    from django.contrib.auth import get_user_model
    User = get_user_model()
    for user_id, tok_set in user_tokens.items():
        activity_by_user[user_id] = get_listing_activity_map(
            User(pk=user_id),
            list(tok_set),
            source_platform=DIVAR_SOURCE_PLATFORM,
        )

    due_ids: list = []
    for listing in base.iterator(chunk_size=500):
        activity_at = activity_by_user.get(listing.dataset.user_id, {}).get(listing.token)
        if is_listing_purge_due(
            listing,
            activity_at=activity_at,
            as_of=as_of,
            cleanup_at=cleanup_at,
        ):
            due_ids.append(listing.pk)
            if limit is not None and len(due_ids) >= limit:
                break
    return due_ids


def purge_eligible_filing_listings_qs(*, as_of=None, force_schedule: bool = False) -> QuerySet:
    if not force_schedule and not is_monthly_cleanup_day(as_of):
        return Listing.objects.none()
    due_ids = _purge_due_listing_ids(as_of=as_of)
    return Listing.objects.filter(pk__in=due_ids)


def _sync_dataset_row_counts(dataset_ids: set) -> None:
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


def build_retention_breakdown(*, as_of=None, force_schedule: bool = False) -> dict:
    base = stale_filing_listings_qs(as_of=as_of)
    share_q = _active_public_share_exists()
    fav_q = _owner_favorite_meta_exists()
    note_q = _owner_meaningful_note_meta_exists()
    tag_q = _owner_workflow_tag_meta_exists()
    customer_q = _customer_listing_relation_exists()
    protected_q = _listing_retention_protection_q()
    inactive_unprotected = base.exclude(protected_q)

    if force_schedule or is_monthly_cleanup_day(as_of):
        final_count = len(_purge_due_listing_ids(as_of=as_of))
    else:
        final_count = 0

    return {
        'cleanup_date': timezone.localtime(current_month_cleanup_datetime(as_of)).date().isoformat(),
        'retention_days': filing_listing_retention_days(),
        'base_inactive_eligible': base.count(),
        'base_age_eligible': base.count(),
        'protected_public_share': base.filter(share_q).count(),
        'protected_favorite': base.filter(fav_q).count(),
        'protected_note': base.filter(note_q).count(),
        'protected_workflow_tag': base.filter(tag_q).count(),
        'protected_customer_relation': base.filter(customer_q).count(),
        'unique_protected': base.filter(protected_q).count(),
        'final_eligible': final_count,
        'scheduled_cleanup_day': is_monthly_cleanup_day(as_of),
    }


def build_listing_meta_audit_counts(*, as_of=None) -> dict:
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
    force_schedule: bool = False,
) -> dict:
    if max_delete is not None and max_delete < 0:
        raise ValueError('max_delete must be non-negative')

    batch_size = max(1, min(batch_size, 5000))
    breakdown = build_retention_breakdown(as_of=None, force_schedule=force_schedule)
    stats = {
        **breakdown,
        'eligible': breakdown['final_eligible'],
        'deleted': 0,
        'affected_datasets': 0,
        'affected_users': 0,
        'batches': 0,
        'remaining_eligible': breakdown['final_eligible'],
        'dry_run': dry_run,
        'batch_size': batch_size,
        'max_delete': max_delete,
        'force_schedule': force_schedule,
    }

    if not force_schedule and not breakdown['scheduled_cleanup_day']:
        stats['skipped_reason'] = 'not_monthly_cleanup_day'
        return stats

    if dry_run or stats['eligible'] == 0 or max_delete == 0:
        return stats

    affected_dataset_ids: set = set()
    affected_user_ids: set = set()
    deleted_listings = 0
    batches = 0
    delete_quota = max_delete
    processed_offset = 0

    while True:
        if delete_quota is not None and delete_quota <= 0:
            break

        fetch_limit = batch_size
        if delete_quota is not None:
            fetch_limit = min(batch_size, delete_quota)

        batch_ids = _purge_due_listing_ids(limit=fetch_limit)
        if not batch_ids:
            break

        with transaction.atomic():
            batch_rows = Listing.objects.filter(pk__in=batch_ids).values_list('dataset_id', 'dataset__user_id')
            batch_dataset_ids = {row[0] for row in batch_rows}
            affected_user_ids.update(row[1] for row in batch_rows)
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
    stats['affected_users'] = len(affected_user_ids)
    stats['batches'] = batches
    stats['remaining_eligible'] = len(_purge_due_listing_ids())
    logger.info(
        'purge_stale_filing_listings deleted=%s eligible=%s datasets=%s batches=%s retention_days=%s',
        stats['deleted'],
        stats['eligible'],
        stats['affected_datasets'],
        stats['batches'],
        stats['retention_days'],
    )
    return stats
