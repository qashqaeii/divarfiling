"""وضعیت retention برای UI/API — منبع واحد حقیقت."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils import timezone

from workspace.models import Listing, ListingMeta, ListingPublicShare
from workspace.constants import WORKFLOW_RETENTION_TAGS
from workspace.services.listing_activity import get_listing_activity_map
from workspace.services.listing_personal_status import DIVAR_SOURCE_PLATFORM
from workspace.services.listing_retention_calendar import (
    current_month_cleanup_datetime,
    days_until_deletion,
    filing_listing_retention_days,
    is_rollout_safe_for_purge,
    scheduled_deletion_at,
    warning_window_start,
)

RETENTION_STATUS_NORMAL = 'normal'
RETENTION_STATUS_WARNING = 'warning'
RETENTION_STATUS_PROTECTED = 'protected'

PROTECTION_PUBLIC_SHARE = 'public_share'
PROTECTION_FAVORITE = 'favorite'
PROTECTION_NOTE = 'note'
PROTECTION_WORKFLOW_TAG = 'workflow_tag'
PROTECTION_CUSTOMER_RELATION = 'customer_relation'


def _customer_listing_relation_exists() -> Exists:
    from workspace.models import CustomerListing

    return Exists(
        CustomerListing.objects.filter(
            token=OuterRef('token'),
            customer__user_id=OuterRef('dataset__user_id'),
        ),
    )


def effective_last_activity_at(
    listing: Listing,
    *,
    activity_at=None,
) -> timezone.datetime:
    baseline = listing.created_at
    if activity_at and activity_at > baseline:
        return activity_at
    return baseline


def _hard_protection_reason(listing: Listing) -> str | None:
    user_id = listing.dataset.user_id
    token = listing.token
    if ListingPublicShare.objects.filter(listing_id=listing.pk, is_active=True).exists():
        return PROTECTION_PUBLIC_SHARE
    meta = ListingMeta.objects.filter(user_id=user_id, token=token).first()
    if meta:
        if meta.is_favorite:
            return PROTECTION_FAVORITE
        if meta.note and meta.note.strip():
            return PROTECTION_NOTE
        if meta.tag in WORKFLOW_RETENTION_TAGS:
            return PROTECTION_WORKFLOW_TAG
    from workspace.models import CustomerListing
    if CustomerListing.objects.filter(token=token, customer__user_id=user_id).exists():
        return PROTECTION_CUSTOMER_RELATION
    return None


def retention_info_for_listing(
    listing: Listing,
    *,
    activity_at=None,
    as_of=None,
) -> dict[str, Any]:
    as_of = as_of or timezone.now()
    retention_days = filing_listing_retention_days()
    if not listing.dataset.is_active:
        return {
            'status': RETENTION_STATUS_NORMAL,
            'retention_days': retention_days,
            'is_protected': False,
        }

    protection = _hard_protection_reason(listing)
    if protection:
        return {
            'status': RETENTION_STATUS_PROTECTED,
            'retention_days': retention_days,
            'is_protected': True,
            'protection_reason': protection,
        }

    if activity_at is None:
        from workspace.models import UserListingActivity

        activity_at = UserListingActivity.objects.filter(
            user_id=listing.dataset.user_id,
            source_platform=DIVAR_SOURCE_PLATFORM,
            external_id=listing.token,
        ).values_list('last_activity_at', flat=True).first()

    effective = effective_last_activity_at(listing, activity_at=activity_at)
    scheduled = scheduled_deletion_at(effective, retention_days=retention_days, as_of=as_of)
    payload: dict[str, Any] = {
        'status': RETENTION_STATUS_NORMAL,
        'retention_days': retention_days,
        'is_protected': False,
        'last_activity_at': effective.isoformat(),
        'scheduled_deletion_at': scheduled.isoformat() if scheduled else None,
        'days_remaining': None,
    }
    if not scheduled:
        return payload

    warn_start = warning_window_start(scheduled)
    if as_of < warn_start:
        return payload

    payload['days_remaining'] = days_until_deletion(scheduled, as_of=as_of)
    payload['status'] = RETENTION_STATUS_WARNING
    return payload


def batch_retention_info_map(
    listings: list[Listing],
    user,
    *,
    as_of=None,
) -> dict[str, dict[str, Any]]:
    if not listings or not user:
        return {}
    tokens = list({lst.token for lst in listings})
    activity_map = get_listing_activity_map(user, tokens, source_platform=DIVAR_SOURCE_PLATFORM)
    return {
        lst.token: retention_info_for_listing(
            lst,
            activity_at=activity_map.get(lst.token),
            as_of=as_of,
        )
        for lst in listings
    }


def retention_info_to_api(info: dict[str, Any]) -> dict[str, Any]:
    out = {
        'status': info.get('status', RETENTION_STATUS_NORMAL),
        'retention_days': info.get('retention_days', filing_listing_retention_days()),
        'is_protected': bool(info.get('is_protected')),
    }
    if info.get('last_activity_at'):
        out['last_activity_at'] = info['last_activity_at']
    if info.get('scheduled_deletion_at'):
        out['scheduled_deletion_at'] = info['scheduled_deletion_at']
    if info.get('days_remaining') is not None:
        out['days_remaining'] = info['days_remaining']
    if info.get('protection_reason'):
        out['protection_reason'] = info['protection_reason']
    return out


def inactive_listings_base_qs(*, as_of=None) -> QuerySet:
    """Listingهای inactive بر اساس effective_last_activity — فقط dataset فعال."""
    from django.db.models import F, Subquery
    from django.db.models.functions import Coalesce, Greatest

    from workspace.models import UserListingActivity

    as_of = as_of or timezone.now()
    cutoff = as_of - timedelta(days=filing_listing_retention_days())
    activity_sq = UserListingActivity.objects.filter(
        user_id=OuterRef('dataset__user_id'),
        source_platform=DIVAR_SOURCE_PLATFORM,
        external_id=OuterRef('token'),
    ).values('last_activity_at')[:1]
    return Listing.objects.filter(dataset__is_active=True).annotate(
        _effective_last=Greatest(
            F('created_at'),
            Coalesce(Subquery(activity_sq), F('created_at')),
        ),
    ).filter(_effective_last__lt=cutoff)


def listing_ids_in_retention_warning(
    user,
    qs: QuerySet | None = None,
    *,
    as_of=None,
) -> list:
    base = qs if qs is not None else Listing.objects.filter(
        dataset__user=user,
        dataset__is_active=True,
    )
    candidates = inactive_listings_base_qs(as_of=as_of).filter(
        pk__in=base.values('pk'),
    ).exclude(
        Exists(ListingPublicShare.objects.filter(listing_id=OuterRef('pk'), is_active=True)),
    )
    activity_map = get_listing_activity_map(
        user,
        list(candidates.values_list('token', flat=True)),
    )
    warning_ids = []
    for listing in candidates.iterator(chunk_size=500):
        if _hard_protection_reason(listing):
            continue
        info = retention_info_for_listing(
            listing,
            activity_at=activity_map.get(listing.token),
            as_of=as_of,
        )
        if info.get('status') == RETENTION_STATUS_WARNING:
            warning_ids.append(listing.pk)
    return warning_ids


def is_listing_purge_due(
    listing: Listing,
    *,
    activity_at=None,
    as_of=None,
    cleanup_at=None,
) -> bool:
    as_of = as_of or timezone.now()
    cleanup_at = cleanup_at or current_month_cleanup_datetime(as_of)
    if _hard_protection_reason(listing):
        return False
    effective = effective_last_activity_at(listing, activity_at=activity_at)
    scheduled = scheduled_deletion_at(
        effective,
        retention_days=filing_listing_retention_days(),
        as_of=as_of,
    )
    if not scheduled or scheduled > cleanup_at:
        return False
    if not is_rollout_safe_for_purge(scheduled, as_of=as_of):
        return False
    return True
