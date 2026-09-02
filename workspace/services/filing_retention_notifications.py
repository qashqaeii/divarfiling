"""اعلان تجمیعی هشدار retention فایلینگ — یک notification به ازای هر user در هر cycle."""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from mobile_api.models import MobileNotification
from mobile_api.services.notification_service import create_notification
from workspace.models import Dataset, Listing
from workspace.services.listing_retention_calendar import (
    current_month_cleanup_datetime,
    days_until_deletion,
    next_monthly_cleanup_datetime,
    warning_window_start,
)
from workspace.services.listing_retention_status import (
    RETENTION_STATUS_WARNING,
    batch_retention_info_map,
    inactive_listings_base_qs,
)

logger = logging.getLogger(__name__)

NOTIFICATION_TYPE = 'filing_retention_warning'


def _cleanup_cycle_key(as_of=None) -> str:
    cleanup = next_monthly_cleanup_datetime(as_of)
    local = timezone.localtime(cleanup)
    return local.date().isoformat()


def _warning_window_active(as_of=None) -> bool:
    as_of = as_of or timezone.now()
    cleanup = next_monthly_cleanup_datetime(as_of)
    return as_of >= warning_window_start(cleanup) and as_of < cleanup


def count_warning_listings_for_user(user, *, as_of=None) -> int:
    as_of = as_of or timezone.now()
    base = Listing.objects.filter(dataset__user=user, dataset__is_active=True)
    candidates = inactive_listings_base_qs(as_of=as_of).filter(pk__in=base.values('pk'))
    count = 0
    chunk: list[Listing] = []
    for listing in candidates.iterator(chunk_size=200):
        chunk.append(listing)
        if len(chunk) >= 100:
            info_map = batch_retention_info_map(chunk, user, as_of=as_of)
            count += sum(1 for info in info_map.values() if info.get('status') == RETENTION_STATUS_WARNING)
            chunk = []
    if chunk:
        info_map = batch_retention_info_map(chunk, user, as_of=as_of)
        count += sum(1 for info in info_map.values() if info.get('status') == RETENTION_STATUS_WARNING)
    return count


def notify_filing_retention_warnings(*, dry_run: bool = False, as_of=None) -> dict:
    as_of = as_of or timezone.now()
    cycle_key = _cleanup_cycle_key(as_of)
    cleanup = next_monthly_cleanup_datetime(as_of)
    stats = {
        'dry_run': dry_run,
        'cycle_key': cycle_key,
        'warning_window_active': _warning_window_active(as_of),
        'cleanup_at': timezone.localtime(cleanup).isoformat(),
        'users_notified': 0,
        'users_with_warnings': 0,
        'notifications_created': 0,
    }
    if not stats['warning_window_active']:
        stats['skipped_reason'] = 'outside_warning_window'
        return stats

    User = get_user_model()
    user_ids = (
        Dataset.objects.filter(is_active=True)
        .values('user_id')
        .annotate(c=Count('id'))
        .filter(c__gt=0)
        .values_list('user_id', flat=True)
    )
    for user_id in user_ids:
        user = User.objects.filter(pk=user_id).first()
        if not user:
            continue
        warning_count = count_warning_listings_for_user(user, as_of=as_of)
        if warning_count <= 0:
            continue
        stats['users_with_warnings'] += 1
        if dry_run:
            continue
        cleanup_local = timezone.localtime(cleanup)
        cleanup_label = cleanup_local.strftime('%d %B')
        title = f'{warning_count} فایل در آستانه پاک‌سازی'
        body = (
            f'{warning_count} فایل بدون فعالیت شما در پاک‌سازی {cleanup_label} '
            'حذف می‌شوند. آن‌ها را بررسی کنید یا به فایل شخصی منتقل کنید.'
        )
        deep_link = 'divarfiling://filing?retention_warning=1'
        before_count = MobileNotification.objects.filter(
            user=user,
            notification_type=NOTIFICATION_TYPE,
        ).count()
        create_notification(
            user,
            notification_type=NOTIFICATION_TYPE,
            title=title,
            body=body,
            deep_link=deep_link,
            data={
                'cycle_key': cycle_key,
                'warning_count': warning_count,
                'cleanup_at': cleanup.isoformat(),
            },
        )
        after_count = MobileNotification.objects.filter(
            user=user,
            notification_type=NOTIFICATION_TYPE,
        ).count()
        if after_count > before_count:
            stats['notifications_created'] += 1
            stats['users_notified'] += 1
        logger.info(
            'filing_retention_warning user=%s count=%s cycle=%s',
            user_id,
            warning_count,
            cycle_key,
        )
    return stats
