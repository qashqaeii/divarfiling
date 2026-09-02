"""ثبت و خواندن آخرین فعالیت معنادار کاربر روی token فایلینگ."""
from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from workspace.models import UserListingActivity
from workspace.services.listing_personal_status import DIVAR_SOURCE_PLATFORM

DEFAULT_SOURCE_PLATFORM = DIVAR_SOURCE_PLATFORM


def touch_listing_activity(
    user,
    external_id: str,
    *,
    source_platform: str = DEFAULT_SOURCE_PLATFORM,
    at=None,
) -> None:
    """فعالیت معنادار کاربر — retention clock را reset می‌کند."""
    if not user or not user.pk or not external_id:
        return
    at = at or timezone.now()
    UserListingActivity.objects.update_or_create(
        user_id=user.pk,
        source_platform=source_platform,
        external_id=external_id,
        defaults={'last_activity_at': at},
    )


def get_listing_activity_map(
    user,
    tokens: list[str],
    *,
    source_platform: str = DEFAULT_SOURCE_PLATFORM,
) -> dict[str, datetime]:
    if not user or not user.pk or not tokens:
        return {}
    return {
        row['external_id']: row['last_activity_at']
        for row in UserListingActivity.objects.filter(
            user_id=user.pk,
            source_platform=source_platform,
            external_id__in=tokens,
        ).values('external_id', 'last_activity_at')
    }
